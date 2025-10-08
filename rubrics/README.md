# Grading Rubrics Directory

This directory contains rubric templates for the AI Grading Agent's RAG system.

## 📋 Format

Each rubric should be a JSON file with the following structure:

```json
{
  "id": "unique_rubric_id",
  "name": "Human-Readable Rubric Name",
  "type": "essay|code|project|presentation",
  "description": "Brief description of what this rubric evaluates",
  "max_score": 100,
  "criteria": [
    {
      "name": "Criterion Name",
      "weight": 0.25,
      "description": "What this criterion evaluates",
      "levels": {
        "Excellent (90-100)": "Description of excellent performance",
        "Good (80-89)": "Description of good performance",
        "Satisfactory (70-79)": "Description of satisfactory performance",
        "Needs Improvement (60-69)": "Description of needs improvement",
        "Unsatisfactory (<60)": "Description of unsatisfactory performance"
      }
    }
  ]
}
```

## 🔍 How It Works

1. **Storage**: Rubrics are stored as JSON files in this directory
2. **Indexing**: On initialization, rubrics are indexed in ChromaDB with vector embeddings
3. **Retrieval**: When grading, the system performs semantic search to find the best matching rubric
4. **Usage**: Retrieved rubrics are used to guide the AI's grading evaluation

## 📚 Available Rubrics

The system includes comprehensive discipline-specific rubrics:

### Computer Science
- **`computer_science_algorithms.json`** - Advanced algorithms & data structures (time/space complexity, optimization)
- **`computer_science_discrete_math.json`** - Discrete mathematics (logic, set theory, proofs, combinatorics, graph theory, number theory)
- **`computer_science_theory_computation.json`** - Theory of computation (automata, formal languages, computability, complexity theory, P vs NP)
- **`computer_science_intro.json`** - Introductory programming (beginner-friendly, focuses on fundamentals)
- **`computer_science_software_project.json`** - Full software engineering projects (design, testing, documentation, security)
- **`code_review_general.json`** - General code review (correctness, quality, efficiency)

### Social Sciences
- **`social_sciences_research_paper.json`** - Advanced research papers with APA/Chicago Author-Date style (methodology, literature review, empirical analysis)
- **`social_sciences_intro.json`** - Introductory essays with basic APA citations (Psychology, Sociology, Political Science, Economics)

### Humanities
- **`humanities_advanced.json`** - Advanced essays with MLA/Chicago style (Literature, History, Philosophy, close reading)
- **`humanities_intro.json`** - Introductory essays with basic MLA citations (analysis vs. summary focus)
- **`history_research_paper.json`** - History research papers with Chicago Notes-Bibliography (primary sources, historiography)

### Mathematics
- **`mathematics_calculus.json`** - All calculus levels (Calc I, II, III, Multivariable) - derivatives, integrals, applications, graphical interpretation
- **`mathematics_proofs.json`** - Introduction to Higher Math, proof-based courses (logic, set theory, proof techniques, abstract algebra, real analysis)
- **`mathematics_intro.json`** - Introductory mathematics (Algebra, Trigonometry, Precalculus) - computational skills and problem-solving

### General
- **`essay_general.json`** - General essay grading (thesis, evidence, organization, style)

## 🎯 Citation Style Guide

### APA 7th Edition (Social Sciences)
- **Used for:** Psychology, Sociology, Political Science, Economics, Education
- **Format:** Author-Date system (Author, Year) or (Author, Year, p. #)
- **Reference Page:** Alphabetized, hanging indents
- **Example:** (Smith, 2020, p. 45)

### MLA 9th Edition (Humanities - Literature)
- **Used for:** Literature, Cultural Studies, Media Studies
- **Format:** Author-Page system (Author page#)
- **Works Cited:** Alphabetized, hanging indents
- **Example:** (Shakespeare 23)

### Chicago Manual of Style (Humanities - History)
- **Used for:** History, Philosophy, Art History
- **Format:** Notes-Bibliography (footnotes/endnotes + bibliography)
- **Bibliography:** Alphabetized, hanging indents
- **Example:** Footnote with full citation first, shortened form after

## 📊 Rubric Selection Guide

### For Introductory Courses (100-200 level)
- `computer_science_intro.json` - Intro programming
- `social_sciences_intro.json` - Intro social science courses
- `humanities_intro.json` - Intro literature/humanities courses
- `mathematics_intro.json` - Intro mathematics (Algebra, Precalculus)

### For Intermediate & Advanced Courses (200-400 level)
- `computer_science_discrete_math.json` - Discrete mathematics (200-300 level)
- `computer_science_algorithms.json` - Advanced algorithms (300-400 level)
- `computer_science_theory_computation.json` - Theory of computation (300-400 level)
- `computer_science_software_project.json` - Capstone projects (400 level)
- `social_sciences_research_paper.json` - Research methods courses
- `humanities_advanced.json` - Upper-level literature/philosophy
- `history_research_paper.json` - Advanced history seminars
- `mathematics_calculus.json` - All calculus courses (100-300 level)
- `mathematics_proofs.json` - Proof-based mathematics (300-400 level)

### By Discipline
**Computer Science:** Intro Programming → Discrete Math → Algorithms → Theory of Computation → Software Projects  
**Social Sciences:** Intro Essay → Research Paper (with empirical analysis)  
**Humanities:** Intro Essay → Advanced Essay → History Research (primary sources)  
**Mathematics:** Intro Math (computational) → Calculus (applications) → Proofs (theoretical)

## ✏️ Creating Custom Rubrics

1. Create a new `.json` file in this directory
2. Follow the format above
3. Restart the agent to re-index rubrics
4. Your rubric will be automatically available via RAG

## 🎯 Example Use Cases

- **Subject-specific**: Create rubrics for specific subjects (history essays, lab reports)
- **Assignment-specific**: Create rubrics for specific assignments (research paper, final project)
- **Course-specific**: Create rubrics tailored to your course requirements

## 🔄 Updating Rubrics

To update rubrics:
1. Modify the JSON file
2. Delete `.chroma_rubrics/` directory
3. Restart the agent to re-index

The rubrics will be re-embedded and searchable immediately.
