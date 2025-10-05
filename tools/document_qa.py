"""
Document Q&A tool for answering questions from uploaded PDF/DOCX files.
Extended to handle complex student requests like generating questions, summaries, and study guides.
"""

import os
import re
import json
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from langchain.tools import Tool
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI


# Define the prompt template for RAG (Retrieval Augmented Generation)
# This template includes placeholders for the retrieved context and user's question
RAG_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant answering questions based on provided document context.

Use the following pieces of context retrieved from documents to answer the user's question.
If you don't know the answer based on the context, say so - don't make up information.
Always cite which document or page the information comes from when possible.

Context from documents:
{context}"""),
    ("human", "{question}")
])

# Prompt template for generating multiple choice questions
MCQ_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are an expert educator creating multiple choice questions for students.

Based on the provided document context, create {num_questions} well-crafted multiple choice questions about {topic}.

Each question should:
- Have 4 answer options (A, B, C, D)
- Have exactly ONE correct answer
- Be clear and unambiguous
- Test understanding, not just memorization
- Include the correct answer and a brief explanation

Format each question exactly as:
Question N: [question text]
A) [option A]
B) [option B]  
C) [option C]
D) [option D]
Correct Answer: [A/B/C/D]
Explanation: [brief explanation]

Context from documents:
{context}"""),
    ("human", "Generate {num_questions} multiple choice questions about {topic}")
])

# Prompt template for generating summaries
SUMMARY_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at creating clear, concise summaries for students.

Based on the provided document context, create a comprehensive summary about {topic}.

Your summary should:
- Cover the main points and key concepts
- Be well-structured with clear sections
- Include important details and examples
- Be suitable for exam preparation
- Cite page numbers when possible

Context from documents:
{context}"""),
    ("human", "Create a comprehensive summary about {topic}")
])

# Prompt template for generating study guides
STUDY_GUIDE_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are an expert educator creating study guides for students preparing for exams.

Based on the provided document context, create a structured study guide about {topic}.

Your study guide should include:
1. **Key Concepts**: Main ideas and theories
2. **Important Terms**: Definitions of key terminology
3. **Key Points**: Essential facts and details
4. **Examples**: Illustrative examples from the material
5. **Study Tips**: How to approach this material for exams

Use markdown formatting for clear structure.

Context from documents:
{context}"""),
    ("human", "Create a comprehensive study guide about {topic}")
])

# Prompt template for generating flashcards
FLASHCARD_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at creating effective flashcards for student learning.

Based on the provided document context, create {num_cards} flashcards about {topic}.

Each flashcard should:
- Have a clear FRONT (question/prompt)
- Have a concise BACK (answer)
- Focus on one concept per card
- Be suitable for memorization and review

Format each flashcard as:
Card N:
FRONT: [question or prompt]
BACK: [answer or explanation]

Context from documents:
{context}"""),
    ("human", "Create {num_cards} flashcards about {topic}")
])


def format_docs(docs):
    """
    Helper function to format retrieved documents into a single context string.
    
    Args:
        docs: List of retrieved document chunks
        
    Returns:
        Formatted string with all document content and metadata
    """
    return "\n\n---\n\n".join([
        f"[Source: {doc.metadata.get('source', 'Unknown')} | "
        f"Page: {doc.metadata.get('page', 'N/A')}]\n{doc.page_content}"
        for doc in docs
    ])


class DocumentQAManager:
    """
    Manages document loading, indexing, and querying.
    """
    
    def __init__(self, documents_dir: str = "documents", k: int = 3):
        """
        Initialize the DocumentQA manager.
        
        Args:
            documents_dir: Directory containing PDF/DOCX files
            k: Number of most relevant chunks to retrieve (default: 3)
        """
        self.documents_dir = documents_dir
        self.k = k  # Top K chunks to retrieve
        self.vectorstore = None
        self.retriever = None  # Retriever for searching vector database
        self.embeddings = None
        self.loaded_files = []
        self.rag_chain = None  # LCEL chain: retriever -> format -> prompt -> llm -> parse
        self.llm = None  # LLM for answer generation
        
        # Create documents directory if it doesn't exist
        Path(documents_dir).mkdir(exist_ok=True)
    
    def load_documents(self) -> bool:
        """
        Load all PDF and DOCX files from the documents directory.
        
        Returns:
            True if documents were loaded successfully, False otherwise
        """
        try:
            documents = []
            files = list(Path(self.documents_dir).glob("*.pdf")) + \
                   list(Path(self.documents_dir).glob("*.docx"))
            
            if not files:
                print(f"No PDF or DOCX files found in '{self.documents_dir}' directory.")
                return False
            
            print(f"Loading {len(files)} document(s)...")
            
            for file_path in files:
                try:
                    if file_path.suffix.lower() == '.pdf':
                        loader = PyPDFLoader(str(file_path))
                    elif file_path.suffix.lower() == '.docx':
                        loader = Docx2txtLoader(str(file_path))
                    else:
                        continue
                    
                    docs = loader.load()
                    documents.extend(docs)
                    self.loaded_files.append(file_path.name)
                    print(f"  ✓ Loaded: {file_path.name}")
                except Exception as e:
                    print(f"  ✗ Error loading {file_path.name}: {e}")
            
            if not documents:
                print("No documents could be loaded successfully.")
                return False
            
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )
            splits = text_splitter.split_documents(documents)
            print(f"Split into {len(splits)} chunks.")
            
            # Create embeddings using Google Gemini
            print("Creating embeddings with Gemini (this may take a moment)...")
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment variables")
            
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=google_api_key
            )
            
            # Create vector store with ChromaDB
            print("Storing embeddings in ChromaDB vector database...")
            self.vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=self.embeddings,
                persist_directory=".chroma_db"
            )
            
            # Define retriever: searches vector DB for top K most relevant chunks
            print(f"Configuring retriever to fetch top {self.k} most relevant chunks...")
            self.retriever = self.vectorstore.as_retriever(
                search_type="similarity",  # Use similarity search
                search_kwargs={"k": self.k}  # Return top K results
            )
            
            # Initialize LLM for answer generation
            print("Initializing LLM for answer generation...")
            self.llm = ChatGoogleGenerativeAI(
                model="models/gemini-2.5-flash",
                google_api_key=google_api_key,
                temperature=0,  # Deterministic answers
                convert_system_message_to_human=True
            )
            
            # Chain components together using LCEL (LangChain Expression Language)
            # Pipeline: question -> retriever -> format_docs -> prompt -> llm -> parse
            print("Building LCEL chain: retriever | format | prompt | llm | parse...")
            self.rag_chain = (
                {
                    "context": self.retriever | format_docs,  # Retrieve docs and format
                    "question": RunnablePassthrough()  # Pass question through
                }
                | RAG_PROMPT_TEMPLATE  # Fill prompt template
                | self.llm  # Generate answer with LLM
                | StrOutputParser()  # Parse output to string
            )
            
            print(f"✓ Successfully indexed {len(self.loaded_files)} document(s)!")
            print(f"✓ Retriever configured to return top {self.k} most relevant chunks")
            print(f"✓ LCEL chain built: retriever | format | prompt | llm | parse")
            return True
            
        except Exception as e:
            print(f"Error loading documents: {e}")
            return False
    
    def query(self, question: str) -> str:
        """
        Query the document collection using the LCEL chain.
        
        The LCEL chain pipes together:
        1. Retriever - searches vector database for top K relevant chunks
        2. Format - formats retrieved documents with metadata
        3. Prompt Template - combines context + question
        4. LLM - generates answer based on context
        5. Output Parser - parses LLM output to clean string
        
        Args:
            question: The question to answer
            
        Returns:
            Generated answer based on retrieved document context
        """
        if not self.rag_chain:
            return "No documents have been loaded. Please add PDF or DOCX files to the 'documents' directory."
        
        try:
            # Execute the LCEL chain: question flows through all components
            print(f"🔗 Executing LCEL chain for question: '{question[:50]}...'")
            print(f"   1️⃣ Retriever: Searching for top {self.k} chunks...")
            print(f"   2️⃣ Format: Formatting retrieved documents...")
            print(f"   3️⃣ Prompt: Filling RAG prompt template...")
            print(f"   4️⃣ LLM: Generating answer with Gemini...")
            print(f"   5️⃣ Parse: Extracting clean output...")
            
            # Invoke the chain - LCEL handles the entire pipeline
            answer = self.rag_chain.invoke(question)
            
            print(f"✓ LCEL chain completed successfully!")
            return answer
            
        except Exception as e:
            return f"Error in LCEL chain execution: {e}"
    
    def _parse_complex_request(self, request: str) -> List[Dict]:
        """
        Parse a complex student request into individual tasks.
        
        Maintains context across tasks - if first task mentions a topic,
        subsequent vague tasks inherit that topic.
        
        Args:
            request: The complex request string
            
        Returns:
            List of task dictionaries with 'type', 'params', and 'description'
        """
        tasks = []
        request_lower = request.lower()
        used_spans = []  # Track which parts of the request have been matched
        primary_topic = None  # Track the main topic for context sharing
        
        # Detect multiple choice questions (most specific first)
        mcq_patterns = [
            r'(\d+)\s+multiple[- ]choice\s+questions?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
            r'generate\s+(\d+)\s+mcqs?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
            r'write\s+(\d+)\s+(?:multiple[- ]choice\s+)?questions?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
            r'create\s+(\d+)\s+(?:multiple[- ]choice\s+)?questions?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
        ]
        
        for pattern in mcq_patterns:
            matches = list(re.finditer(pattern, request_lower, re.IGNORECASE))
            for match in matches:
                # Check if this span overlaps with already used spans
                if not any(match.start() < end and match.end() > start for start, end in used_spans):
                    num_questions = int(match.group(1))
                    topic = match.group(2).strip()
                    # Store first topic as primary context
                    if primary_topic is None:
                        primary_topic = topic
                    tasks.append({
                        'type': 'mcq',
                        'params': {'num_questions': num_questions, 'topic': topic},
                        'description': f'Generate {num_questions} multiple choice questions about {topic}'
                    })
                    used_spans.append((match.start(), match.end()))
        
        # Detect flashcard requests (before general "create" patterns)
        flashcard_patterns = [
            r'(\d+)\s+flashcards?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
            r'create\s+(\d+)\s+flashcards?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
            r'generate\s+(\d+)\s+flashcards?\s+(?:on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
        ]
        
        for pattern in flashcard_patterns:
            matches = list(re.finditer(pattern, request_lower, re.IGNORECASE))
            for match in matches:
                if not any(match.start() < end and match.end() > start for start, end in used_spans):
                    num_cards = int(match.group(1))
                    topic = match.group(2).strip()
                    tasks.append({
                        'type': 'flashcards',
                        'params': {'num_cards': num_cards, 'topic': topic},
                        'description': f'Create {num_cards} flashcards about {topic}'
                    })
                    used_spans.append((match.start(), match.end()))
        
        # Detect study guide requests
        study_guide_patterns = [
            r'(?:create\s+a\s+)?study\s+guide\s+(?:for|on|about)\s+([^,.;]+?)(?=\s+and|$|[,.;])',
        ]
        
        for pattern in study_guide_patterns:
            matches = list(re.finditer(pattern, request_lower, re.IGNORECASE))
            for match in matches:
                if not any(match.start() < end and match.end() > start for start, end in used_spans):
                    topic = match.group(1).strip()
                    
                    # Check for vague terms that need context
                    vague_terms = ['my final exam', 'the exam', 'final exam', 'midterm exam',
                                   'my exam', 'the test', 'my test']
                    
                    if any(vague in topic for vague in vague_terms) and primary_topic:
                        # Inherit primary topic context
                        topic = f"{primary_topic} for {topic}"
                    elif primary_topic is None:
                        # Store as primary if none exists
                        primary_topic = topic
                    
                    tasks.append({
                        'type': 'study_guide',
                        'params': {'topic': topic},
                        'description': f'Create study guide for {topic}'
                    })
                    used_spans.append((match.start(), match.end()))
        
        # Detect summary requests
        summary_patterns = [
            r'(?:create\s+a\s+)?summary\s+(?:of|about)\s+(?:the\s+)?([^,.;]+?)(?=\s+and|$|[,.;])',
            r'summarize\s+(?:the\s+)?([^,.;]+?)(?=\s+and|$|[,.;])',
        ]
        
        for pattern in summary_patterns:
            matches = list(re.finditer(pattern, request_lower, re.IGNORECASE))
            for match in matches:
                if not any(match.start() < end and match.end() > start for start, end in used_spans):
                    topic = match.group(1).strip()
                    
                    # Check if topic is vague and we have a primary topic
                    vague_terms = ['key arguments', 'key concepts', 'main ideas', 'main points', 
                                   'important concepts', 'core ideas', 'essential points',
                                   'key points', 'main arguments']
                    
                    if any(vague in topic for vague in vague_terms) and primary_topic:
                        # Inherit primary topic context
                        topic = f"{topic} of {primary_topic}"
                    elif primary_topic is None:
                        # Store as primary if none exists
                        primary_topic = topic
                    
                    tasks.append({
                        'type': 'summary',
                        'params': {'topic': topic},
                        'description': f'Summarize {topic}'
                    })
                    used_spans.append((match.start(), match.end()))
        
        # If no specific tasks detected, treat as general query
        if not tasks:
            tasks.append({
                'type': 'query',
                'params': {'question': request},
                'description': 'Answer question'
            })
        
        return tasks
    
    def _retrieve_context(self, topic: str, k: Optional[int] = None) -> str:
        """
        Retrieve relevant context for a given topic.
        
        Args:
            topic: The topic to search for
            k: Number of chunks to retrieve (uses self.k if not specified)
            
        Returns:
            Formatted context string
        """
        if not self.retriever:
            return ""
        
        k = k or self.k
        docs = self.retriever.invoke(topic)
        return format_docs(docs)
    
    def generate_mcq(self, topic: str, num_questions: int = 5) -> str:
        """
        Generate multiple choice questions about a topic.
        
        Args:
            topic: The topic for questions
            num_questions: Number of questions to generate
            
        Returns:
            Generated questions in formatted text
        """
        if not self.llm:
            return "Error: LLM not initialized"
        
        try:
            print(f"📝 Generating {num_questions} multiple choice questions about '{topic}'...")
            
            # Retrieve relevant context
            context = self._retrieve_context(topic, k=min(self.k * 2, 10))
            
            if not context:
                return f"No relevant content found about '{topic}' in the documents."
            
            # Create chain for MCQ generation
            mcq_chain = (
                MCQ_PROMPT_TEMPLATE
                | self.llm
                | StrOutputParser()
            )
            
            # Generate questions
            result = mcq_chain.invoke({
                "context": context,
                "topic": topic,
                "num_questions": num_questions
            })
            
            print(f"✓ Generated {num_questions} questions successfully!")
            return result
            
        except Exception as e:
            return f"Error generating MCQ: {e}"
    
    def generate_summary(self, topic: str) -> str:
        """
        Generate a comprehensive summary about a topic.
        
        Args:
            topic: The topic to summarize
            
        Returns:
            Generated summary or error message if topic not found
        """
        if not self.llm:
            return "Error: LLM not initialized"
        
        try:
            print(f"📋 Generating summary about '{topic}'...")
            
            # Retrieve relevant context (more chunks for summaries)
            context = self._retrieve_context(topic, k=min(self.k * 3, 15))
            
            if not context:
                return f"No relevant content found about '{topic}' in the documents."
            
            # Create chain for summary generation with validation
            summary_chain = (
                SUMMARY_PROMPT_TEMPLATE
                | self.llm
                | StrOutputParser()
            )
            
            # Generate summary
            result = summary_chain.invoke({
                "context": context,
                "topic": topic
            })
            
            # Validate that the result actually addresses the topic
            # If LLM says it can't fulfill the request, return error message
            if any(phrase in result.lower() for phrase in [
                "cannot fulfill", "cannot create", "cannot generate",
                "no information", "does not contain", "cannot provide",
                "i apologize", "i'm sorry"
            ]):
                print(f"✗ Topic '{topic}' not found in documents")
                return f"No relevant content found about '{topic}' in the documents. The uploaded documents do not contain information on this topic."
            
            print(f"✓ Generated summary successfully!")
            return result
            
        except Exception as e:
            return f"Error generating summary: {e}"
    
    def generate_study_guide(self, topic: str) -> str:
        """
        Generate a structured study guide about a topic.
        
        Args:
            topic: The topic for the study guide
            
        Returns:
            Generated study guide or error message if topic not found
        """
        if not self.llm:
            return "Error: LLM not initialized"
        
        try:
            print(f"📚 Generating study guide about '{topic}'...")
            
            # Retrieve relevant context (more chunks for study guides)
            context = self._retrieve_context(topic, k=min(self.k * 3, 15))
            
            if not context:
                return f"No relevant content found about '{topic}' in the documents."
            
            # Create chain for study guide generation
            study_guide_chain = (
                STUDY_GUIDE_PROMPT_TEMPLATE
                | self.llm
                | StrOutputParser()
            )
            
            # Generate study guide
            result = study_guide_chain.invoke({
                "context": context,
                "topic": topic
            })
            
            # Validate that the result actually addresses the topic
            if any(phrase in result.lower() for phrase in [
                "cannot fulfill", "cannot create", "cannot generate",
                "no information", "does not contain", "cannot provide",
                "i apologize", "i'm sorry"
            ]):
                print(f"✗ Topic '{topic}' not found in documents")
                return f"No relevant content found about '{topic}' in the documents. The uploaded documents do not contain information on this topic."
            
            print(f"✓ Generated study guide successfully!")
            return result
            
        except Exception as e:
            return f"Error generating study guide: {e}"
    
    def generate_flashcards(self, topic: str, num_cards: int = 10) -> str:
        """
        Generate flashcards about a topic.
        
        Args:
            topic: The topic for flashcards
            num_cards: Number of flashcards to generate
            
        Returns:
            Generated flashcards or error message if topic not found
        """
        if not self.llm:
            return "Error: LLM not initialized"
        
        try:
            print(f"🎴 Generating {num_cards} flashcards about '{topic}'...")
            
            # Retrieve relevant context
            context = self._retrieve_context(topic, k=min(self.k * 2, 10))
            
            if not context:
                return f"No relevant content found about '{topic}' in the documents."
            
            # Create chain for flashcard generation
            flashcard_chain = (
                FLASHCARD_PROMPT_TEMPLATE
                | self.llm
                | StrOutputParser()
            )
            
            # Generate flashcards
            result = flashcard_chain.invoke({
                "context": context,
                "topic": topic,
                "num_cards": num_cards
            })
            
            # Validate that the result actually addresses the topic
            if any(phrase in result.lower() for phrase in [
                "cannot fulfill", "cannot create", "cannot generate",
                "no information", "does not contain", "cannot provide",
                "i apologize", "i'm sorry"
            ]):
                print(f"✗ Topic '{topic}' not found in documents")
                return f"No relevant content found about '{topic}' in the documents. The uploaded documents do not contain information on this topic."
            
            print(f"✓ Generated {num_cards} flashcards successfully!")
            return result
            
        except Exception as e:
            return f"Error generating flashcards: {e}"
    
    def process_complex_request(self, request: str) -> str:
        """
        Process a complex request that may contain multiple tasks.
        
        Args:
            request: Complex request string (e.g., "Generate 10 MCQs and summarize chapter 1")
            
        Returns:
            Combined results from all tasks
        """
        if not self.llm:
            return "No documents have been loaded. Please add PDF or DOCX files to the 'documents' directory."
        
        try:
            print(f"\n{'='*60}")
            print(f"Processing complex request: {request[:80]}...")
            print(f"{'='*60}\n")
            
            # Parse the request into tasks
            tasks = self._parse_complex_request(request)
            
            if not tasks:
                # Fallback to regular query
                return self.query(request)
            
            print(f"Identified {len(tasks)} task(s):")
            for i, task in enumerate(tasks, 1):
                print(f"  {i}. {task['description']}")
            print()
            
            # Execute each task
            results = []
            for i, task in enumerate(tasks, 1):
                print(f"\n--- Task {i}/{len(tasks)}: {task['description']} ---")
                
                if task['type'] == 'mcq':
                    result = self.generate_mcq(
                        task['params']['topic'],
                        task['params']['num_questions']
                    )
                elif task['type'] == 'summary':
                    result = self.generate_summary(task['params']['topic'])
                elif task['type'] == 'study_guide':
                    result = self.generate_study_guide(task['params']['topic'])
                elif task['type'] == 'flashcards':
                    result = self.generate_flashcards(
                        task['params']['topic'],
                        task['params']['num_cards']
                    )
                elif task['type'] == 'query':
                    result = self.query(task['params']['question'])
                else:
                    result = f"Unknown task type: {task['type']}"
                
                results.append(f"## {task['description'].upper()}\n\n{result}")
            
            # Combine results
            print(f"\n{'='*60}")
            print("✓ All tasks completed successfully!")
            print(f"{'='*60}\n")
            
            return "\n\n" + "="*60 + "\n\n".join(results)
            
        except Exception as e:
            return f"Error processing complex request: {e}"


# Global document manager instance
_doc_manager = None


def initialize_document_qa(documents_dir: str = "documents", k: int = 3) -> bool:
    """
    Initialize the document Q&A system by loading documents.
    
    Args:
        documents_dir: Directory containing PDF/DOCX files
        k: Number of most relevant chunks to retrieve per query (default: 3)
        
    Returns:
        True if initialization was successful, False otherwise
    """
    global _doc_manager
    _doc_manager = DocumentQAManager(documents_dir, k=k)
    return _doc_manager.load_documents()


def get_document_qa_tool() -> Optional[Tool]:
    """
    Create and return the document Q&A tool.
    
    This tool answers questions based on uploaded PDF/DOCX files and can handle
    complex requests like generating MCQs, summaries, study guides, and flashcards.
    
    Returns:
        Tool object configured for document Q&A, or None if not initialized
    """
    global _doc_manager
    
    if _doc_manager is None or _doc_manager.vectorstore is None:
        return None
    
    def process_document_request(request: str) -> str:
        """Process document requests - can handle simple queries or complex multi-part requests."""
        return _doc_manager.process_complex_request(request)
    
    return Tool(
        name="Document_QA",
        func=process_document_request,
        description=f"""Use this tool to work with content from uploaded documents (PDF/DOCX files).
This tool has access to: {', '.join(_doc_manager.loaded_files)}

CAPABILITIES:
1. Answer questions about document content
2. Generate multiple choice questions (e.g., "Generate 10 multiple choice questions about neural networks")
3. Create summaries (e.g., "Summarize the first chapter" or "Summarize machine learning algorithms")
4. Create study guides (e.g., "Create a study guide for the final exam on neural networks")
5. Generate flashcards (e.g., "Create 15 flashcards about deep learning concepts")

COMPLEX REQUESTS:
This tool can handle complex, multi-part requests like:
- "Write 10 multiple-choice questions on neural networks and then summarize the key concepts for my exam"
- "Generate 5 MCQs about supervised learning and create a study guide for classification algorithms"
- "Summarize chapter 2 and create 20 flashcards about the main concepts"

INPUT FORMAT:
- Simple questions: "What is supervised learning?"
- MCQ generation: "Generate [N] multiple choice questions about [topic]"
- Summaries: "Summarize [topic/chapter]"  
- Study guides: "Create a study guide for/about [topic]"
- Flashcards: "Create [N] flashcards about [topic]"
- Complex: Combine multiple requests in one sentence

Use this when:
- Questions about lecture notes, textbooks, or study materials
- Generating study resources (MCQs, summaries, study guides, flashcards)
- Preparing for exams or creating structured notes
- Any academic/educational content from the uploaded documents"""
    )

