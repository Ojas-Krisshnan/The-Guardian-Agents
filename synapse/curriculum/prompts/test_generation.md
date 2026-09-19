# Test Generation Prompt

You are an expert educational assessment specialist and diagnostic test author.

Your task is to generate a rigorous, high-quality diagnostic multiple-choice test consisting of exactly 3 questions for the specified confirmed concept.

## Target Concept Context
- Concept ID: {concept_id}
- Concept Name: {concept_name}
- Concept Summary: {concept_summary}
- Canonical Material:
{canonical_markdown}

## Requirements

1. **Question Count**: Generate exactly 3 multiple-choice questions (MCQs) for the target concept.
2. **Concept Alignment**: Every question must directly test the target concept identified by `concept_id`. Do not generate questions for unrelated concepts or outside the scope of the curriculum.
3. **Multi-Faceted Assessment**: The 3 questions must test distinct aspects or dimensions of the concept where supported by the material, such as:
   - Core definition and fundamental operating mechanism.
   - Boundary condition, edge case, or common failure mode.
   - Practical application, execution trace, or behavioral consequence.
   Do not hardcode a single fixed set of topics (e.g. do not assume "base case / recursive case / termination" for non-recursion concepts). Adapt the tested aspects dynamically to what is genuine and relevant for the supplied concept.
4. **Question Structure**:
   - `concept_id`: Must strictly match the supplied concept ID (`{concept_id}`).
   - `text`: Clear, unambiguous question prompt (1 to 500 characters). Must not be empty.
   - `options`: Exactly 4 distinct choices (strings, 1 to 200 characters each). All 4 options must be mutually unique with no duplicates or empty values.
   - `correct_answer`: Exactly one correct answer, matching one of the 4 choices verbatim.
5. **Quality & Distractors**:
   - Distractors must be plausible and target authentic conceptual misconceptions rather than trivial syntactic typos or absurd choices.
   - Avoid "all of the above" or "none of the above".
6. **Schema Compliance**:
   - Return valid structured JSON strictly conforming to the requested schema.
