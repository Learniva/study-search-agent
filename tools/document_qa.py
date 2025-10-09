"""
Document Q&A Tool using RAG (Retrieval-Augmented Generation) with LangGraph.

Enables Q&A over uploaded documents using ChromaDB and embeddings.

AI Fundamentals Applied:
- RAG: Retrieval-Augmented Generation for answering questions from documents
- Vector embeddings: Semantic search through document content
- ChromaDB: Persistent vector store for document knowledge base
- LangGraph: Multi-step workflow for document processing and answer generation

Architecture:
    START → enhance_query → retrieve_documents → generate_answer → format_sources → END
"""

import os
from typing import Optional, TypedDict, Annotated, List, Dict, Any
from pathlib import Path
from langchain.tools import Tool

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# Global document QA components
_doc_qa_graph = None
_doc_vectorstore = None
_doc_embeddings = None
_doc_llm = None


class DocumentQAState(TypedDict):
    """
    LangGraph State for Document Q&A workflow.
    
    Tracks the multi-step RAG process from query to final answer.
    """
    query: str  # Original user query
    enhanced_query: Optional[str]  # Enhanced query for better retrieval
    is_chapter_query: bool  # Whether this is a chapter/section query
    is_study_material: bool  # Whether generating study materials
    retrieved_documents: Optional[List[Any]]  # Retrieved document chunks
    answer: Optional[str]  # Generated answer
    sources: Optional[List[Dict[str, Any]]]  # Source documents with metadata
    final_answer: Optional[str]  # Final formatted answer with sources


class DocumentQAGraph:
    """
    LangGraph-based Document Q&A system.
    
    Implements a multi-step RAG workflow:
    1. Query enhancement (improve retrieval quality)
    2. Document retrieval (MMR search for diverse results)
    3. Answer generation (LLM synthesis with prompt engineering)
    4. Source formatting (citations and references)
    """
    
    def __init__(self, vectorstore, llm):
        """
        Initialize the Document Q&A graph.
        
        Args:
            vectorstore: ChromaDB vectorstore with indexed documents
            llm: Language model for answer generation
        """
        self.vectorstore = vectorstore
        self.llm = llm
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow for document Q&A.
        
        Graph structure:
        START → enhance_query → retrieve_documents → generate_answer → format_sources → END
        """
        workflow = StateGraph(DocumentQAState)
        
        # Add nodes
        workflow.add_node("enhance_query", self._enhance_query_node)
        workflow.add_node("retrieve_documents", self._retrieve_documents_node)
        workflow.add_node("generate_answer", self._generate_answer_node)
        workflow.add_node("format_sources", self._format_sources_node)
        
        # Set entry point
        workflow.set_entry_point("enhance_query")
        
        # Add edges (linear flow for RAG)
        workflow.add_edge("enhance_query", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "generate_answer")
        workflow.add_edge("generate_answer", "format_sources")
        workflow.add_edge("format_sources", END)
        
        return workflow.compile()
    
    def _enhance_query_node(self, state: DocumentQAState) -> DocumentQAState:
        """
        LangGraph Node: Enhance query for better retrieval.
        
        Detects chapter queries and study material requests to add
        specific instructions for content-focused retrieval.
        """
        query = state["query"]
        
        # Detect if query is about a chapter or section
        is_chapter_query = any(keyword in query.lower() for keyword in ["chapter", "section", "part"])
        
        # Detect the type of request
        is_study_material = any(keyword in query.lower() for keyword in 
                               ["study guide", "flashcard", "summary", "mcq", "quiz", "test", "notes"])
        
        enhanced_query = query
        
        if is_chapter_query or is_study_material:
            # Add explicit content instructions (no hardcoded topics)
            enhanced_query = f"""{query}

CRITICAL INSTRUCTIONS FOR RETRIEVAL:
1. Search for the ACTUAL CONTENT and EXPLANATIONS from the requested section
2. AVOID table of contents, chapter titles, and page number listings
3. Focus on substantive educational content: concepts, definitions, examples, algorithms
4. If a chapter is requested, find pages that EXPLAIN topics from that chapter, not pages that just MENTION the chapter
5. Extract and present SPECIFIC knowledge from the document"""
            
            print(f"   🔍 Enhanced query for content-focused retrieval")
        
        return {
            **state,
            "enhanced_query": enhanced_query,
            "is_chapter_query": is_chapter_query,
            "is_study_material": is_study_material
        }
    
    def _retrieve_documents_node(self, state: DocumentQAState) -> DocumentQAState:
        """
        LangGraph Node: Retrieve relevant documents using MMR.
        
        Uses Maximal Marginal Relevance for diverse, comprehensive results.
        Retrieves 40 chunks for rich context.
        """
        enhanced_query = state["enhanced_query"]
        
        print(f"   📚 Retrieving documents with MMR (k=40)...")
        
        # Use MMR for diverse results
        retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 40,  # Return 40 most relevant chunks
                "fetch_k": 100,  # Consider 100 candidates before selecting 40
                "lambda_mult": 0.7  # Favor relevance slightly over diversity
            }
        )
        
        retrieved_docs = retriever.get_relevant_documents(enhanced_query)
        
        print(f"   ✅ Retrieved {len(retrieved_docs)} document chunks")
        
        return {
            **state,
            "retrieved_documents": retrieved_docs
        }
    
    def _generate_answer_node(self, state: DocumentQAState) -> DocumentQAState:
        """
        LangGraph Node: Generate answer using LLM with retrieved context.
        
        Uses a carefully crafted prompt that focuses on extracting
        actual content rather than metadata.
        """
        query = state["query"]
        retrieved_docs = state["retrieved_documents"]
        
        # Build context from retrieved documents
        context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        
        # Create prompt template
        prompt_template = """You are an expert educational AI assistant. Extract and teach ACTUAL CONTENT from documents.

CRITICAL RULES:
1. IGNORE: table of contents, chapter titles, page listings, prefaces
2. FOCUS ON: concepts, definitions, explanations, examples, algorithms, formulas
3. If you receive mostly metadata (chapter titles, page numbers) with NO substantive content:
   - Be HONEST: Say "The retrieved text contains mainly chapter references, not actual content"
   - RECOMMEND: Suggest asking about specific TOPICS rather than chapter numbers
   - Example: Instead of "chapter 12", ask "explain GANs and generative models"

4. For study materials, extract SPECIFIC knowledge:
   - Concepts with clear definitions
   - HOW mechanisms work (not just WHAT they are)
   - Examples, applications, technical details
   
5. Page numbers in sources: Check if they match the requested chapter/section
   - If asked about "chapter 12" but sources show page 25, that's likely WRONG retrieval
   - Acknowledge this: "Note: Sources appear to be from early chapters, not chapter 12"

Context from documents:
{context}

Question: {question}

Your answer (be honest about content quality):"""

        # Format prompt with context and question
        formatted_prompt = prompt_template.format(context=context, question=query)
        
        print(f"   🧠 Generating answer with LLM...")
        
        # Generate answer using LLM
        messages = [
            SystemMessage(content="You are an expert educational AI assistant focused on extracting and teaching actual content from documents."),
            HumanMessage(content=formatted_prompt)
        ]
        
        response = self.llm.invoke(messages)
        answer = response.content
        
        return {
            **state,
            "answer": answer
        }
    
    def _format_sources_node(self, state: DocumentQAState) -> DocumentQAState:
        """
        LangGraph Node: Format answer with source citations.
        
        Adds references to source documents for transparency and verification.
        """
        answer = state["answer"]
        retrieved_docs = state["retrieved_documents"]
        
        # Extract unique sources
        sources_list = []
        seen_sources = set()
        
        for doc in retrieved_docs[:10]:  # Show top 10 unique sources
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            source_key = f"{source}:{page}" if page else source
            
            if source not in seen_sources:
                source_info = {"source": source, "page": page}
                sources_list.append(source_info)
                seen_sources.add(source)
        
        # Format sources section
        if sources_list:
            source_info = f"\n\n📚 Sources (from {len(retrieved_docs)} chunks retrieved):"
            for src in sources_list:
                if src["page"]:
                    source_info += f"\n  • {src['source']} (page {src['page']})"
                else:
                    source_info += f"\n  • {src['source']}"
            
            if len(retrieved_docs) > len(sources_list):
                source_info += f"\n  ... and {len(retrieved_docs) - len(sources_list)} more chunks"
            
            final_answer = answer + source_info
        else:
            final_answer = answer
        
        return {
            **state,
            "sources": sources_list,
            "final_answer": final_answer
        }
    
    def query(self, question: str) -> str:
        """
        Process a question through the LangGraph workflow.
        
        Args:
            question: User's question about the documents
            
        Returns:
            Final answer with source citations
        """
        try:
            # Initial state
            initial_state: DocumentQAState = {
                "query": question,
                "enhanced_query": None,
                "is_chapter_query": False,
                "is_study_material": False,
                "retrieved_documents": None,
                "answer": None,
                "sources": None,
                "final_answer": None
            }
            
            # Run the graph
            result = self.graph.invoke(initial_state)
            
            return result["final_answer"]
            
        except Exception as e:
            error_msg = f"❌ Error in document Q&A workflow: {str(e)}"
            print(f"⚠️  Document QA error: {e}")
            return error_msg


def initialize_document_qa(documents_dir: str = "documents") -> bool:
    """
    Initialize document Q&A system with LangGraph workflow.
    
    This loads documents (PDFs, DOCX) and indexes them for semantic search,
    then creates a LangGraph workflow for multi-step RAG processing.
    Uses Google's embeddings for consistency with the rest of the system.
    
    Args:
        documents_dir: Directory containing documents to index
        
    Returns:
        True if successful, False otherwise
    """
    global _doc_qa_graph, _doc_vectorstore, _doc_embeddings, _doc_llm
    
    try:
        # Check if documents exist
        docs_path = Path(documents_dir)
        if not docs_path.exists() or not any(docs_path.iterdir()):
            print(f"⚠️  No documents found in {documents_dir}")
            return False
        
        # Try to import required libraries (graceful degradation)
        try:
            from langchain_community.vectorstores import Chroma
            from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
            from langchain.chains import RetrievalQA
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain_core.documents import Document
            
            # Try PyMuPDF (fitz) for better PDF extraction
            try:
                import fitz  # PyMuPDF
                PYMUPDF_AVAILABLE = True
                print("   ✅ Using PyMuPDF for PDF extraction (superior quality)")
            except ImportError:
                PYMUPDF_AVAILABLE = False
                from langchain_community.document_loaders import PyPDFLoader
                print("   ⚠️  PyMuPDF not available, using PyPDFLoader (install with: pip install pymupdf)")
            
            # Use Docx2txtLoader for DOCX extraction (Textract has broken dependencies)
            TEXTRACT_AVAILABLE = False
            from langchain_community.document_loaders import Docx2txtLoader
            print("   ✅ Using docx2txt for DOCX extraction (reliable and maintained)")
                
        except ImportError as e:
            print(f"⚠️  Document Q&A dependencies not available: {e}")
            print("   Install with: pip install langchain-google-genai chromadb pymupdf textract")
            return False
        
        # Check for Google API key
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("⚠️  GOOGLE_API_KEY not found. Cannot initialize document embeddings.")
            return False
        
        # Load documents
        print(f"📚 Loading documents from {documents_dir}...")
        
        documents = []
        
        # Load PDFs with PyMuPDF (fitz) for superior extraction
        try:
            pdf_files = list(docs_path.glob("**/*.pdf"))
            
            if PYMUPDF_AVAILABLE:
                # Use PyMuPDF for best quality extraction
                import re
                for pdf_file in pdf_files:
                    try:
                        # Open PDF with PyMuPDF
                        pdf_document = fitz.open(str(pdf_file))
                        
                        for page_num in range(len(pdf_document)):
                            page = pdf_document[page_num]
                            
                            # Extract text with layout preservation
                            text = page.get_text("text", sort=True)
                            
                            # Clean text
                            text = text.strip()
                            
                            # Skip empty or very short pages
                            if len(text) < 50:
                                continue
                            
                            # Try to detect chapter number from page content
                            chapter_patterns = [
                                r'Chapter\s+(\d+)',
                                r'CHAPTER\s+(\d+)',
                                r'^(\d+)\.\s+[A-Z]',  # "12. Generative Deep Learning"
                            ]
                            
                            detected_chapter = None
                            for pattern in chapter_patterns:
                                match = re.search(pattern, text[:500])  # Check first 500 chars
                                if match:
                                    detected_chapter = match.group(1)
                                    break
                            
                            # Create Document with metadata
                            metadata = {
                                'source': str(pdf_file),
                                'page': page_num,
                                'total_pages': len(pdf_document),
                                'file_name': pdf_file.name
                            }
                            
                            if detected_chapter:
                                metadata['chapter'] = int(detected_chapter)
                            
                            doc = Document(
                                page_content=text,
                                metadata=metadata
                            )
                            documents.append(doc)
                        
                        pdf_document.close()
                        
                    except Exception as e:
                        print(f"   ⚠️  Could not load {pdf_file.name}: {e}")
            else:
                # Fallback to PyPDFLoader
                for pdf_file in pdf_files:
                    try:
                        loader = PyPDFLoader(str(pdf_file), extract_images=False)
                        pdf_pages = loader.load()
                        
                        for page in pdf_pages:
                            content = page.page_content.strip()
                            if content and len(content) > 50:
                                documents.append(page)
                                
                    except Exception as e:
                        print(f"   ⚠️  Could not load {pdf_file.name}: {e}")
            
            if documents:
                pdf_count = len([d for d in documents if '.pdf' in d.metadata.get('source', '')])
                print(f"   📄 Loaded {len(pdf_files)} PDF file(s), {pdf_count} pages (PyMuPDF: {PYMUPDF_AVAILABLE})")
        except Exception as e:
            print(f"   ⚠️  Could not load PDFs: {e}")
        
        # Load DOCX files with docx2txt (reliable extraction)
        try:
            docx_files = list(docs_path.glob("**/*.docx"))
            
            for docx_file in docx_files:
                try:
                    loader = Docx2txtLoader(str(docx_file))
                    docx_content = loader.load()
                    
                    for doc in docx_content:
                        content = doc.page_content.strip()
                        if content and len(content) > 50:
                            # Ensure proper metadata
                            if 'file_name' not in doc.metadata:
                                doc.metadata['file_name'] = docx_file.name
                            documents.append(doc)
                            
                except Exception as e:
                    print(f"   ⚠️  Could not load {docx_file.name}: {e}")
            
            if docx_files:
                docx_count = len([d for d in documents if '.docx' in d.metadata.get('source', '')])
                print(f"   📝 Loaded {len(docx_files)} DOCX file(s), {docx_count} sections")
        except Exception as e:
            print(f"   ⚠️  Could not load DOCX files: {e}")
        
        if not documents:
            print(f"⚠️  No documents could be loaded from {documents_dir}")
            return False
        
        print(f"✅ Loaded {len(documents)} total document(s)")
        
        # Split documents into smaller, more granular chunks for better retrieval
        print("🔄 Splitting documents into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,  # Smaller chunks for more granular retrieval
            chunk_overlap=200,  # Overlap to preserve context across boundaries
            length_function=len,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " ", ""],  # Natural boundaries
            keep_separator=True  # Keep separators for better context
        )
        texts = text_splitter.split_documents(documents)
        
        # Filter out very small or empty chunks
        texts = [chunk for chunk in texts if len(chunk.page_content.strip()) > 100]
        
        print(f"   Created {len(texts)} text chunks (filtered, avg ~{800} chars each)")
        print(f"   This ensures rich context with 40+ chunks per query")
        
        # Create embeddings using Google's embedding model (VERIFIED)
        print("🔤 Creating embeddings with Google Generative AI...")
        print(f"   📊 Embedding Model: models/embedding-001 (Google)")
        _doc_embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",  # Google's text embedding model
            google_api_key=google_api_key
        )
        print("   ✅ Google embeddings initialized successfully")
        
        # Create vector store
        print("💾 Storing documents in ChromaDB...")
        _doc_vectorstore = Chroma.from_documents(
            documents=texts,
            embedding=_doc_embeddings,
            persist_directory=".chroma_docs",
            collection_name="document_qa"
        )
        
        # Create LLM (consistent with other tools - using gemini-2.5-flash)
        _doc_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            google_api_key=google_api_key,
            convert_system_message_to_human=True
        )
        
        print("   🧠 LLM initialized: gemini-2.5-flash (temperature=0.3)")
        
        # Create LangGraph workflow for Document Q&A
        print("🔧 Building LangGraph workflow for Document Q&A...")
        _doc_qa_graph = DocumentQAGraph(
            vectorstore=_doc_vectorstore,
            llm=_doc_llm
        )
        
        print("   🎯 LangGraph nodes: enhance_query → retrieve_documents → generate_answer → format_sources")
        print("   📊 Retrieval: MMR with k=40 chunks per query")
        
        print(f"✅ Document Q&A initialized with LangGraph ({len(documents)} documents, {len(texts)} chunks)")
        return True
    
    except Exception as e:
        print(f"❌ Error initializing document Q&A: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_document_qa_tool() -> Optional[Tool]:
    """
    Get Document Q&A tool with LangGraph-based RAG workflow.
    
    This tool enables RAG-based question answering over uploaded documents
    using a multi-step LangGraph workflow for better quality results.
    Returns None if the document store hasn't been initialized.
    
    Returns:
        Tool object or None if not available
    """
    global _doc_qa_graph
    
    def query_documents(question: str) -> str:
        """
        Query the document knowledge base using LangGraph RAG workflow.
        
        This executes a multi-step process:
        1. Query enhancement for better retrieval
        2. Document retrieval (MMR, k=40)
        3. Answer generation with LLM
        4. Source formatting
        
        Args:
            question: Question to answer from documents
            
        Returns:
            Answer with source citations when available
        """
        if _doc_qa_graph is None:
            return "⚠️  No documents have been loaded. Please upload and index documents first."
        
        try:
            # Use LangGraph workflow to process the question
            print(f"   🚀 Running LangGraph workflow for Document Q&A...")
            answer = _doc_qa_graph.query(question)
            return answer
            
        except Exception as e:
            error_msg = f"❌ Error querying documents: {str(e)}"
            print(f"⚠️  Document QA error: {e}")
            return error_msg
    
    # Only return tool if documents are loaded
    if _doc_qa_graph is not None:
        return Tool(
            name="Document_QA",
            func=query_documents,
            description="""Use this tool to answer questions from uploaded documents using RAG (Retrieval-Augmented Generation) with LangGraph.

This tool uses a multi-step LangGraph workflow:
1. Query enhancement for better retrieval
2. Semantic search through document knowledge base (MMR, k=40 chunks)
3. LLM-based answer generation
4. Source citation formatting

Best for:
- Questions about specific documents the user has uploaded (PDFs, DOCX)
- Information from study materials, lecture notes, or textbooks
- Academic papers and research content
- References to "my notes", "the document", "uploaded files"
- Finding specific information in large document collections
- Generating study materials (flashcards, summaries, MCQs) from documents

Input: A clear, specific question about the document content
Output: Answer based on the documents with source citations

Examples:
- "What is the main thesis of the uploaded paper?"
- "Summarize chapter 3 from my notes"
- "What does the document say about machine learning?"
- "Create flashcards for chapter 5"
- "Generate 10 MCQs from this section"

ONLY use this tool if the user explicitly mentions documents, notes, or uploaded files.
Do NOT use for general knowledge questions - use Web_Search instead."""
        )
    
    print("⚠️  Document Q&A tool not available - no documents loaded")
    return None
