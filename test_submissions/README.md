# Test Submissions & Sample Grading Commands

This directory contains sample student submissions for testing the grading agent across various disciplines and rubrics.

## ⚠️ IMPORTANT: How to Use These Commands

**The `$(cat ...)` syntax ONLY works when run from the shell/terminal, NOT in interactive mode.**

### ✅ Method 1: Use --question flag (RECOMMENDED)
```bash
source study_agent/bin/activate
python main.py --role professor --question "Grade this essay: $(cat test_submissions/essay_good.txt)"
```

### ✅ Method 2: Use the helper script
```bash
./grade_sample.sh essay_good.txt
./grade_sample.sh cs_algorithm_sorting.py
```

### ❌ This WILL NOT WORK (in interactive mode):
```
[TEACHER] Your request: Grade this: $(cat test_submissions/essay_good.txt)
```
The `$(...)` command substitution doesn't work inside Python's interactive prompt!

---

## Quick Start Examples

```bash
# Grade an essay (using --question flag)
python main.py --role professor \
  --question "Grade this essay: $(cat test_submissions/essay_good.txt)"

# Review code (using helper script)
./grade_sample.sh code_sample.py
```

---

## Computer Science Submissions

### 1. Algorithm Implementation (Sorting)
**File:** `cs_algorithm_sorting.py`  
**Rubric:** `rubrics/computer_science_algorithms.json`

```bash
# Grade with algorithm rubric
python main.py --role professor --user-id prof123 \
  --question "Grade this sorting algorithm implementation using the algorithms rubric: $(cat test_submissions/cs_algorithm_sorting.py)"

# Or use rubric retrieval
python main.py --role professor \
  --question "Evaluate this algorithm assignment: $(cat test_submissions/cs_algorithm_sorting.py)"
```

### 2. Discrete Mathematics Problems
**File:** `cs_discrete_math_problems.txt`  
**Rubric:** `rubrics/computer_science_discrete_math.json`

```bash
python main.py --role professor \
  --question "Grade this discrete math assignment: $(cat test_submissions/cs_discrete_math_problems.txt)"
```

### 3. Theory of Computation (Automata)
**File:** `cs_theory_computation_automata.txt`  
**Rubric:** `rubrics/computer_science_theory_computation.json`

```bash
python main.py --role professor \
  --question "Evaluate this theory of computation assignment: $(cat test_submissions/cs_theory_computation_automata.txt)"
```

### 4. Introductory Programming
**File:** `intro_programming_assignment.py`  
**Rubric:** `rubrics/computer_science_intro.json`

```bash
python main.py --role professor \
  --question "Grade this intro programming assignment: $(cat test_submissions/intro_programming_assignment.py)"

# Quick code review without rubric
python main.py --role professor \
  --question "Review this Python code: $(cat test_submissions/intro_programming_assignment.py)"
```

### 5. General Code Sample
**File:** `code_sample.py`

```bash
# Quick code review
python main.py --role professor \
  --question "Review this code for correctness and style: $(cat test_submissions/code_sample.py)"
```

---

## Mathematics Submissions

### 6. Calculus Assignment
**File:** `math_calculus_assignment.txt`  
**Rubric:** `rubrics/mathematics_calculus.json`

```bash
python main.py --role professor \
  --question "Grade this calculus assignment: $(cat test_submissions/math_calculus_assignment.txt)"
```

---

## Social Sciences Submissions

### 7. Psychology Research Paper
**File:** `social_sciences_psychology_research.txt`  
**Rubric:** `rubrics/social_sciences_research_paper.json`  
**Citation Style:** APA

```bash
# Grade with social sciences rubric
python main.py --role professor \
  --question "Grade this psychology research paper with APA citations: $(cat test_submissions/social_sciences_psychology_research.txt)"

# Check APA citation format
python main.py --role professor \
  --question "Check the APA citation format in this paper: $(cat test_submissions/social_sciences_psychology_research.txt)"
```

---

## Humanities Submissions

### 8. Literature Analysis Essay
**File:** `humanities_literature_analysis.txt`  
**Rubric:** `rubrics/humanities_advanced.json`  
**Citation Style:** MLA

```bash
python main.py --role professor \
  --question "Grade this literature analysis with MLA citations: $(cat test_submissions/humanities_literature_analysis.txt)"
```

### 9. History Research Paper
**File:** `history_research_paper_chicago.txt`  
**Rubric:** `rubrics/history_research_paper.json`  
**Citation Style:** Chicago

```bash
python main.py --role professor \
  --question "Grade this history research paper with Chicago citations: $(cat test_submissions/history_research_paper_chicago.txt)"

# Focus on citation format
python main.py --role professor \
  --question "Evaluate the Chicago-style citations in this history paper: $(cat test_submissions/history_research_paper_chicago.txt)"
```

---

## General Essays

### 10. Good Essay Sample
**File:** `essay_good.txt`  
**Rubric:** `rubrics/essay_general.json`

```bash
# Grade with general essay rubric
python main.py --role professor \
  --question "Grade this essay: $(cat test_submissions/essay_good.txt)"

# Custom rubric criteria
python main.py --role professor \
  --question "Evaluate using rubric: Thesis(30%), Evidence(30%), Organization(20%), Grammar(20%). Essay: $(cat test_submissions/essay_good.txt)"
```

### 11. Essay Needs Work
**File:** `essay_needs_work.txt`

```bash
python main.py --role professor \
  --question "Grade this essay and provide constructive feedback: $(cat test_submissions/essay_needs_work.txt)"
```

### 12. Lab Report
**File:** `lab_report.txt`

```bash
python main.py --role professor \
  --question "Grade this lab report focusing on methodology and analysis: $(cat test_submissions/lab_report.txt)"
```

---

## Advanced Grading Techniques

### Using Specific Rubrics

```bash
# Retrieve and use a specific rubric
python main.py --role professor \
  --question "Use the computer science algorithms rubric to grade: $(cat test_submissions/cs_algorithm_sorting.py)"
```

### Custom Evaluation Criteria

```bash
# Define custom criteria
python main.py --role professor \
  --question "Evaluate with criteria: Correctness(40%), Efficiency(30%), Code Style(20%), Documentation(10%). Code: $(cat test_submissions/code_sample.py)"
```

### Comparative Grading

```bash
# Compare two submissions
python main.py --role professor \
  --question "Compare these two essays and explain which is stronger: 
  Essay 1: $(cat test_submissions/essay_good.txt)
  
  Essay 2: $(cat test_submissions/essay_needs_work.txt)"
```

### Feedback Only (No Score)

```bash
# Generate constructive feedback without numerical score
python main.py --role professor \
  --question "Provide detailed feedback on this submission without assigning a grade: $(cat test_submissions/essay_needs_work.txt)"
```

### Citation Style Checking

```bash
# APA style check
python main.py --role professor \
  --question "Check APA citation format: $(cat test_submissions/social_sciences_psychology_research.txt)"

# MLA style check
python main.py --role professor \
  --question "Check MLA citation format: $(cat test_submissions/humanities_literature_analysis.txt)"

# Chicago style check
python main.py --role professor \
  --question "Check Chicago citation format: $(cat test_submissions/history_research_paper_chicago.txt)"
```

---

## Batch Grading

### Grade Multiple Submissions

```bash
# Create a script for batch grading
cat > grade_all.sh << 'EOF'
#!/bin/bash
for file in test_submissions/*.txt; do
  echo "Grading: $file"
  python main.py --role professor \
    --question "Grade this submission: $(cat $file)" \
    >> grading_results.txt
  echo "---" >> grading_results.txt
done
EOF

chmod +x grade_all.sh
./grade_all.sh
```

---

## Using the API

### REST API Examples

```bash
# Grade essay via API
curl -X POST http://localhost:8000/grade \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"submission\": \"$(cat test_submissions/essay_good.txt | jq -Rs .)\",
    \"rubric\": \"essay_general\",
    \"user_id\": \"prof123\"
  }"

# Review code via API
curl -X POST http://localhost:8000/grade \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"submission\": \"$(cat test_submissions/code_sample.py | jq -Rs .)\",
    \"rubric\": \"code_review_general\",
    \"user_id\": \"prof123\"
  }"
```

---

## Programmatic Usage

### Python Script

```python
from agents.supervisor_agent import SupervisorAgent

# Initialize
supervisor = SupervisorAgent()

# Read submission
with open('test_submissions/essay_good.txt', 'r') as f:
    essay = f.read()

# Grade
result = supervisor.query(
    question=f"Grade this essay: {essay}",
    user_role="professor",
    user_id="prof123"
)

print(result['answer'])
```

---

## Tips

1. **Role Required**: Always use `--role professor` or `--role teacher` for grading
2. **User ID**: Use `--user-id` to track grading history in the database
3. **Rubric Selection**: The system can auto-select rubrics based on content, or you can specify one
4. **Citation Styles**: Mention the expected citation style (APA, MLA, Chicago) for better evaluation
5. **File Size**: For large submissions, consider using the API or programmatic approach

---

## Available Rubrics

- `rubrics/essay_general.json` - General essay grading
- `rubrics/code_review_general.json` - General code review
- `rubrics/computer_science_algorithms.json` - Algorithm assignments
- `rubrics/computer_science_intro.json` - Intro CS courses
- `rubrics/computer_science_discrete_math.json` - Discrete math
- `rubrics/computer_science_theory_computation.json` - Theory of computation
- `rubrics/mathematics_intro.json` - Intro mathematics
- `rubrics/mathematics_calculus.json` - Calculus courses
- `rubrics/mathematics_proofs.json` - Proof-based math
- `rubrics/social_sciences_research_paper.json` - Social science papers (APA)
- `rubrics/social_sciences_intro.json` - Intro social sciences
- `rubrics/humanities_advanced.json` - Advanced humanities (MLA)
- `rubrics/humanities_intro.json` - Intro humanities
- `rubrics/history_research_paper.json` - History papers (Chicago)

See `rubrics/README.md` for detailed rubric documentation.

