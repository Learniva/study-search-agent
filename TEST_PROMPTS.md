# Test Prompts for Streaming + Source Citation Verification

## 🎯 Purpose
Test prompts to verify:
1. ✅ Streaming indicators work correctly
2. ✅ Source citations are included
3. ✅ Multi-step synthesis preserves references
4. ✅ Complex queries handled properly

---

## 📝 Test Categories

### 1. Simple Query (Baseline - No Sources Expected)
**Prompt:**
```
What is 2+2?
```
**Expected:**
- Fast response
- No web search needed
- No sources required
- Streaming should still work

---

### 2. Web Search Required (Sources MUST Appear)
**Prompt:**
```
What are the latest developments in quantum computing in 2024?
```
**Expected:**
- Web search triggered (Tavily fallback)
- Multiple sources cited
- References section at the end
- Streaming indicators: SEARCHING, ANALYZING, SYNTHESIZING

---

### 3. Multi-Step Complex Query (Tests Synthesis + Sources)
**Prompt:**
```
Explain quantum entanglement and provide 3 real-world applications with examples
```
**Expected:**
- Multiple web searches
- Synthesis of results
- References section with multiple URLs
- Streaming indicators throughout
- Numbered citations [1], [2], [3] in text

---

### 4. Educational Content (Lesson Plan - Tests Structure + Sources)
**Prompt:**
```
Create a lesson plan on photosynthesis with 10 flashcards
```
**Expected:**
- Structured lesson plan
- 10 flashcards
- References section
- Educational sources cited
- Streaming indicators: PLANNING, SEARCHING, GENERATING

---

### 5. Research Question (Tests Deep Search + Multiple Sources)
**Prompt:**
```
What is the difference between machine learning and deep learning? Include examples of each.
```
**Expected:**
- Clear explanation
- Multiple examples
- 3-5 sources cited
- References section
- Technical accuracy

---

### 6. Current Events (Tests Tavily Fallback)
**Prompt:**
```
Explain the impact of artificial intelligence on healthcare in 2024
```
**Expected:**
- Recent information (Tavily should handle this well)
- Multiple healthcare sources
- References with URLs
- Real-world examples

---

### 7. Comparison Query (Tests Multi-Source Synthesis)
**Prompt:**
```
Compare supervised learning vs unsupervised learning with 3 examples of each
```
**Expected:**
- Clear comparison structure
- 6 total examples (3 each)
- Technical sources cited
- References section

---

### 8. Tutorial Request (Tests Step-by-Step + Sources)
**Prompt:**
```
How do I implement a simple neural network in Python? Provide a basic code example.
```
**Expected:**
- Step-by-step explanation
- Code example
- Sources for learning materials
- References to tutorials/documentation

---

## 🧪 How to Test

### Using Interactive CLI:
```bash
cd /Users/maniko/study-search-agent
source study_agent/bin/activate
python main.py --role professor
```

Then paste each prompt one at a time and verify:

### ✅ Success Criteria for Each Test:
1. **Streaming**: Response appears gradually, not all at once
2. **Indicators**: See messages like:
   - 🔍 SEARCHING
   - 🧠 ANALYZING  
   - ✍️ SYNTHESIZING
   - ✅ COMPLETE
3. **Sources**: Response ends with:
   ```
   ### References
   [1] Title - https://url1.com
   [2] Title - https://url2.com
   [3] Title - https://url3.com
   ```
4. **Inline Citations**: See `[1]`, `[2]`, `[3]` references in the text
5. **Quality**: Response is comprehensive and accurate

---

## 📊 Quick Verification Checklist

After each prompt, check:
- [ ] Did I see streaming indicators?
- [ ] Was the response delivered gradually?
- [ ] Is there a "References" or "Sources" section?
- [ ] Are there URLs in the references?
- [ ] Are there inline citations [1], [2], [3]?
- [ ] Is the content accurate and relevant?

---

## 🎯 Recommended Test Order

1. **Start Simple**: Test prompt #1 (2+2) - verify basic streaming works
2. **Add Complexity**: Test prompt #2 (quantum computing) - verify web search + sources
3. **Multi-Step**: Test prompt #3 (quantum entanglement) - verify synthesis + sources
4. **Your Original**: Test prompt #4 (lesson plan) - verify the fix we just made
5. **Edge Cases**: Test remaining prompts to verify consistency

---

## 🔍 What to Look For

### ❌ FAILURE Signs:
- No "References" or "Sources" section when web search was used
- No URLs in the response
- Response appears all at once (no streaming)
- No streaming indicators

### ✅ SUCCESS Signs:
- Gradual response delivery (streaming)
- "References" section with URLs
- Inline citations [1], [2], [3]
- Streaming indicators showing workflow stages
- Accurate, comprehensive content

---

## 💡 Pro Tips

1. **Watch the Console**: You'll see indicators like:
   ```
   🔍 Searching with Google Custom Search (Primary)...
   🔍 Falling back to Tavily Search...
   ✅ Tavily search successful (fallback)
   ```

2. **Count Sources**: Complex queries should have 3-5 sources minimum

3. **Check Inline Citations**: Good responses cite sources throughout, not just at the end

4. **Verify URLs Work**: Spot-check a few URLs to ensure they're real sources

---

## 🚀 Quick Test Script

For rapid testing, copy-paste this into your terminal:
```bash
# Test 1: Simple
echo "What is 2+2?"

# Test 2: Web Search
echo "What are the latest developments in quantum computing in 2024?"

# Test 3: Complex
echo "Explain quantum entanglement and provide 3 real-world applications"

# Test 4: Original Query
echo "Create a lesson plan on photosynthesis with 10 flashcards"
```

Then paste each prompt into the interactive mode one at a time.

---

**Ready to test! 🎉**

Pick any prompt above and paste it into your running `main.py` session.

