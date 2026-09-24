from nlp_pretrained.ner_tagger import extract_entities


# --------------------------------------------------
# TEST 1: Multiple people + organizations + locations
# --------------------------------------------------

text1 = """
Elon Musk met Sundar Pichai in California to discuss
Tesla, Google, and artificial intelligence.
"""

result1 = extract_entities(text1)

print("\n========== TEST 1 ==========")
print("Text:", text1)
print("Entities:", result1)


# --------------------------------------------------
# TEST 2: Same sentence contains different entity types
# --------------------------------------------------

text2 = """
Narendra Modi visited New York after meeting Microsoft
CEO Satya Nadella and Apple executives.
"""

result2 = extract_entities(text2)

print("\n========== TEST 2 ==========")
print("Text:", text2)
print("Entities:", result2)


# --------------------------------------------------
# TEST 3: Multiple locations and organizations
# --------------------------------------------------

text3 = """
Ratan Tata travelled from Mumbai to London and later
visited the headquarters of Tata Group and Microsoft.
"""

result3 = extract_entities(text3)

print("\n========== TEST 3 ==========")
print("Text:", text3)
print("Entities:", result3)


# --------------------------------------------------
# TEST 4: Difficult sentence with many entities
# --------------------------------------------------

text4 = """
Tim Cook announced that Apple will expand its operations
in India, while Mark Zuckerberg discussed Meta's plans
during a meeting in New Delhi.
"""

result4 = extract_entities(text4)

print("\n========== TEST 4 ==========")
print("Text:", text4)
print("Entities:", result4)


# --------------------------------------------------
# TEST 5: Long and confusing sentence
# --------------------------------------------------

text5 = """
During his visit to Washington, Sundar Pichai spoke with
Joe Biden about Google's investment in the United States,
while Elon Musk announced new Tesla projects in Texas.
"""

result5 = extract_entities(text5)

print("\n========== TEST 5 ==========")
print("Text:", text5)
print("Entities:", result5)