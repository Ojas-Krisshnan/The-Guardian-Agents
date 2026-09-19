---
title: "SYNAPSE CYCLE — COMPLETE WORKFLOW REPORT"
subtitle: "An AI-Assisted Adaptive Learning Pipeline & Contract-Driven Engine"
date: "19/09/2026"

submitted_by:
  - name: "Roshan Kumar K"
  - name: "Yazhvendhan K M"
  - name: "Ojaskrisshnan S"
  - name: "Muhammed Sheik"
  - name: "Aadhisesha D"
---
 

---

<div style="page-break-after: always;"></div>

## 1. PROJECT OVERVIEW

Synapse Cycle is an AI-assisted adaptive learning system designed to support a complete learning cycle between teachers and students.

The system takes teacher-provided learning material, extracts and validates concepts, generates diagnostic tests, evaluates student responses, identifies learning gaps, creates personalized learning guidance, collects teacher feedback where required, and finally produces student- and class-level analytics.

The complete workflow is implemented as a state-driven pipeline, allowing each stage to operate independently while sharing common contracts, persistence, callback, LLM, and runtime infrastructure.

The system follows the **Contracts v2.0** architecture, which defines clear boundaries between the shared core, curriculum, diagnosis, agents, analytics, runtime, API, and frontend layers.

---

## 2. HIGH-LEVEL SYSTEM WORKFLOW

The complete Synapse learning cycle can be represented as:

```text
Teacher Setup
      ↓
Curriculum & Test Generation
      ↓
Student Attempt
      ↓
Diagnosis
      ↓
Tailoring
      ↓
Review
      ↓
Note Saved
      ↓
Analytics
      ↓
Class Analytics & Concept Graph
      ↓
API / Web Application
      ↓
Teacher / Student Frontend
```

The workflow is controlled by the Synapse state machine, ensuring that each operation occurs only in valid states.

---

## 3. SHARED ARCHITECTURE AND CONTRACTS

The system is built around a shared contract foundation that allows all modules to communicate using consistent data structures.

The major shared components include:

```text
synapse/
├── schemas.py
├── state_machine.py
├── api_contracts.py
├── types.ts
└── analytics/
```

The shared contracts define structures such as:

- `ConceptNode`
- `Diagnosis`
- `AnalysisPayload`
- `ClassAnalytics`
- `ConceptGraph`
- `GraphEdge`
- `NoteVersion`
- `TrendLabel`

These shared contracts prevent individual modules from creating incompatible representations of the same information.

The analytics layer consumes diagnosis information and produces `ClassAnalytics` and `ConceptGraph` objects that can subsequently be consumed by the API and frontend layers.

---

## 4. TEACHER SETUP

The workflow begins with the teacher providing canonical learning material.

```text
Teacher
   ↓
Canonical Notes
   ↓
Curriculum Processing
```

The teacher's notes become the source material for concept extraction and diagnostic test generation.

The system maintains a deterministic representation of the curriculum so that subsequent stages can link questions, diagnoses, notes, and analytics back to specific concepts.

---

## 5. CURRICULUM AND CONCEPT EXTRACTION

The curriculum module processes canonical teacher notes using AI-assisted concept extraction.

The extraction process produces structured `ConceptNode` objects containing:

- Stable concept IDs
- Concept names
- Summaries
- Prerequisite relationships

The generated concepts are validated before entering the learning pipeline.

Validation handles:

- Duplicate concepts
- Missing information
- Malformed AI responses
- Invalid prerequisites
- Cyclic dependencies

This ensures that the curriculum entering the learning pipeline is structurally valid.

---

## 6. TEACHER-IN-THE-LOOP CONCEPT CONFIRMATION

Extracted concepts are not blindly accepted.

The system introduces a teacher confirmation stage:

```text
AI Concept Extraction
        ↓
Tag Confirmation
        ↓
   ┌───────────────┐
   │               │
Confirm          Edit
   │               │
   └───────┬───────┘
           ↓
Confirmed Curriculum
```

A shared callback mechanism allows the teacher to confirm or modify extracted concepts.

A deterministic timeout mechanism is also provided so that the workflow does not remain indefinitely suspended.

Once concepts are confirmed or edited, they are passed to test generation.

---

## 7. DIAGNOSTIC TEST GENERATION

The confirmed curriculum is used to generate a diagnostic test.

By default, the system generates:

> **3 concept-linked MCQs**

Each question contains:

- A question statement
- Exactly four unique options
- A validated correct answer
- A relationship to a curriculum concept

The system validates AI-generated responses before accepting them.

Bounded retries are used when the generated output is invalid.

```text
Generate Question
        ↓
     Validate
        ↓
   ┌─────┴─────┐
   │           │
 Valid       Invalid
   │           │
   ↓           ↓
 Accept      Retry
               ↓
          Retry Limit
```

This prevents uncontrolled or infinite model calls.

---

## 8. TEST READY → AWAITING STUDENT

After successful test generation, the state machine transitions the workflow into:

```text
TEST_READY
      ↓
AWAITING_STUDENT
```

The system is now ready to receive the student's attempt.

The runtime ensures that student submissions are accepted only when the run is in the appropriate state.

---

## 9. STUDENT ATTEMPT

The student receives the generated diagnostic test and submits their answers.

The workflow then moves to:

```text
AWAITING_STUDENT
        ↓
ATTEMPT_RECEIVED
```

The submitted attempt becomes the input to the diagnosis stage.

The runtime also maintains run-level information such as:

- Current state
- Cycle
- Revision count
- Model-call information
- Completion metadata
- Errors

---

## 10. DIAGNOSIS

The diagnosis stage analyses the student's response and identifies the nature of mistakes.

The system can distinguish between different types of errors, including:

- `conceptual_gap`
- `careless_mistake`
- `contradictory`
- `unrelated`

The diagnosis provides structured information that is passed to subsequent tailoring and analytics stages.

This allows the system to distinguish between a student who fundamentally lacks a concept and a student who made an isolated mistake.

---

## 11. TAILORING

The diagnosis becomes the basis for personalized learning guidance.

```text
Student Attempt
      ↓
  Diagnosis
      ↓
   Tailoring
      ↓
Personalized Learning Content
```

The system uses the identified learning gaps and relevant concepts to determine what the student should focus on next.

The concept relationships established during curriculum processing and analytics can support prerequisite-aware learning.

---

## 12. REVIEW AND HUMAN FEEDBACK

The workflow contains a review stage where generated learning output can be checked.

The system supports a human-in-the-loop mechanism through persisted callbacks.

The callback workflow allows the system to enter a waiting state and later resume after the required response is provided.

```text
Active Workflow
      ↓
Awaiting Human Input
      ↓
Callback Response
      ↓
Resume Workflow
```

Deterministic timeout and persisted resume behaviour prevent the workflow from becoming permanently blocked.

---

## 13. NOTE SAVING

After the learning and review stage, the resulting learning information is stored as a note.

```text
REVIEWING
    ↓
NOTE_SAVED
```

The system maintains note versions so that later analytics can work with the appropriate version rather than blindly combining outdated information.

This is particularly important for the concept graph, where the latest valid student note is used when constructing the student's current concept representation.

---

## 14. STUDENT ANALYTICS

After the note is saved, the workflow enters the analytics stage:

```text
NOTE_SAVED
    ↓
ANALYSING
```

The analytics layer converts diagnosis information into measurable learning information.

### 14.1 Mastery Calculation

The system starts with:

$$\text{Mastery} = 1.0$$

and applies penalties based on diagnosed mistakes:

| Mistake Type | Penalty |
| :--- | :--- |
| **Conceptual gap** | $-0.25$ |
| **Careless mistake** | $-0.10$ |
| **Contradictory** | $-0.15$ |
| **Unrelated** | $-0.05$ |
| **Empty / no meaningful diagnosis** | $-0.05$ |

The final mastery is constrained to:

$$0.0 \le \text{mastery} \le 1.0$$

#### Examples:
- **No mistakes:** $\to 1.00$
- **One conceptual gap:** $\to 0.75$
- **One careless mistake:** $\to 0.90$
- **One contradictory answer:** $\to 0.85$
- **One unrelated answer:** $\to 0.95$

---

## 15. LEARNING TREND CALCULATION

The system also determines how mastery changes over time.

```text
Previous Mastery
       ↓
    Compare
       ↓
Current Mastery
       ↓
     Trend
```

Possible trend labels include:

- `NEW`
- `IMPROVING`
- `DECLINING`
- `STILL_WEAK`
- `STABLE`

The system uses defined thresholds to distinguish meaningful improvement or decline from normal variation.

This provides a temporal view of student learning rather than relying only on a single mastery score.

---

## 16. CONCEPT GRAPH CONSTRUCTION

The analytics layer also creates a graph representing the student's concept relationships.

Student notes can contain explicit concept references such as:

```text
[[Variables]]
[[Loops]]
[[Functions]]
```

These references are parsed deterministically.

```text
Student Notes
      ↓
Concept References
      ↓
Concept Nodes
      ↓
Graph Edges
      ↓
Concept Graph
```

Unknown concepts are ignored while valid isolated concepts are retained.

The latest note version is used to avoid building the graph from stale information.

---

## 17. GRAPH-BASED LEARNING PATH

The concept graph supports three important operations:

1. `get_prerequisites()`
2. `topological_sort()`
3. `get_learning_path()`

For example:

```text
Variables
    ↓
  Loops
    ↓
Functions
```

The system can determine that `Variables` and `Loops` should be considered before `Functions`.

Topological sorting provides an ordering that respects these dependencies.

Cycle detection ensures that invalid relationships such as:

```text
A → B
↑   ↓
└── C
```

are rejected.

The learning path therefore becomes:

```text
Prerequisites
      ↓
Correct Learning Order
      ↓
Target Concept
```

---

## 18. CLASS-LEVEL ANALYTICS

Individual student analytics are aggregated to generate a class-level view.

```text
Student 1 → Mastery + Trend
Student 2 → Mastery + Trend
Student 3 → Mastery + Trend
Student 4 → Mastery + Trend
              ↓
          Aggregation
              ↓
        Class Analytics
```

Class analytics include:

- Number of students
- Average mastery
- Trend distribution
- Weak students

A student is considered weak when:

$$\text{mastery} < 0.5$$

The aggregation therefore converts individual learning information into information useful for teachers and classroom-level decision making.

---

## 19. STATE MACHINE INTEGRATION

All major operations are connected through the Synapse state machine.

The complete state sequence is:

```text
TEACHER_SETUP
      ↓
TAG_CONFIRMATION
      ↓
TEST_READY
      ↓
AWAITING_STUDENT
      ↓
ATTEMPT_RECEIVED
      ↓
DIAGNOSING
      ↓
TAILORING
      ↓
REVIEWING
      ↓
NOTE_SAVED
      ↓
ANALYSING
      ↓
AGGREGATING
      ↓
COMPLETE
```

The analytics module is integrated specifically into:

```text
NOTE_SAVED
      ↓
ANALYSING
      ↓
AGGREGATING
      ↓
COMPLETE
```

During these stages, the system produces analytical records such as:

- `ANALYSIS`
- `CLASS_ANALYTICS`
- `CONCEPT_GRAPH`

---

## 20. RUNTIME AND PERSISTENCE

The runtime layer coordinates the state machine and manages execution of individual learning runs.

Important runtime behaviour includes:

- Per-run locking
- State validation
- Cycle management
- Revision tracking
- Completion metadata
- Error handling
- Persisted callbacks
- Resume behaviour

After a cycle completes, the system can start another student cycle:

```text
COMPLETE
    ↓
AWAITING_STUDENT
    ↓
cycle += 1
```

This allows Synapse to support repeated learning cycles rather than treating one test as the end of the student's learning journey.

---

## 21. API AND APPLICATION LAYER

The backend exposes the learning workflow through FastAPI.

The API provides functionality for:

- `POST /runs`
- `GET  /runs`
- `GET  /runs/{run_id}`
- `GET  /runs/{run_id}/history`
- `GET  /runs/{run_id}/replay`
- `POST /runs/{run_id}/advance`

The system also provides question and callback operations:

- `GET  /runs/{run_id}/questions`
- `GET  /questions/{question_id}`
- `POST /questions/{question_id}/answer`

This allows the frontend to interact with the workflow without directly accessing the internal state-machine implementation.

---

## 22. AUTHENTICATION AND ROLE-BASED ACCESS

The application supports separate teacher and student roles.

```text
                  Login
                    ↓
          ┌─────────┴─────────┐
          ↓                   ↓
       Teacher             Student
          ↓                   ↓
  Teacher Dashboard   Student Dashboard
```

JWT authentication is used for session authorization.

Role restrictions are enforced at the backend as well as the frontend.

### Teacher Capabilities:
- Create runs
- View runs
- Advance workflows
- View expert questions
- Answer questions
- Resume workflows
- View replay history

### Student Capabilities:
- View runs
- View questions
- Advance permitted workflows
- View completed status
- View replay information

*Note: Students do not receive access to teacher-only functionality.*

---

## 23. FRONTEND WORKFLOW

The frontend provides separate experiences for teachers and students.

### 23.1 Teacher Workflow

```text
Login
  ↓
Teacher Dashboard
  ↓
Create / View Run
  ↓
Advance Workflow
  ↓
View Questions
  ↓
Provide Feedback
  ↓
Resume Workflow
  ↓
View Completion / Replay
```

### 23.2 Student Workflow

```text
Login
  ↓
Student Dashboard
  ↓
View Run
  ↓
View Test / Question
  ↓
Submit Attempt
  ↓
Wait for Processing
  ↓
View Result / Replay
```

The frontend communicates with the FastAPI backend through the defined API contracts.

---

## 24. DETERMINISTIC TESTING ARCHITECTURE

A major design principle throughout the system is deterministic testing.

The project provides stubs and fixtures so that the workflow can be tested without requiring:

- Live LLM calls
- Network access
- External APIs
- API keys

For example:

```text
Real LLM                Deterministic Stub
   ↓                            ↓
Production execution       Testing / CI
```

The curriculum module includes deterministic curriculum stubs, prompts, canonical-note fixtures, and test fixtures.

The analytics layer similarly provides deterministic fixtures and tests.

This allows the complete pipeline to be executed and validated in an isolated environment.

---

## 25. TESTING AND VERIFICATION

The project contains testing at multiple levels.

### 25.1 Unit Testing

Individual functions are tested independently, including:

- Mastery calculation
- Trend calculation
- Aggregation
- Concept parsing
- Graph construction
- Graph algorithms
- Curriculum validation
- Test generation
- State transitions
- API behaviour
- Authentication
- Role-based access

The analytics and graph implementation contains:
- **35 tests** | **35 passed**

Contract tests:
- **15 tests** | **15 passed**

The documented repository verification for the analytics implementation resulted in:
- **50 passed, 0 failures**

### 25.2 Integration Testing

Integration tests verify the interaction between modules:

```text
Teacher Setup
      ↓
Curriculum
      ↓
Test Generation
      ↓
Student Attempt
      ↓
Diagnosis
      ↓
Tailoring
      ↓
Review
      ↓
Analytics
      ↓
Completion
```

### 25.3 API Testing

The API tests verify:

- Authentication
- Run creation
- Run listing
- Run retrieval
- Run advancement
- Question retrieval
- Teacher responses
- Callback handling
- Replay
- Error handling
- Role restrictions

### 25.4 Frontend Testing

Frontend tests verify:

- Login
- Student dashboard
- Teacher dashboard
- Run creation
- Run selection
- Run advancement
- Expert questions
- Teacher answers
- Answer state changes
- Replay
- Error handling
- Role protection

---

## 26. ARCHITECTURE VERIFICATION

The project also verifies module boundaries.

The analytics layer is kept independent from unrelated application layers such as:

- API
- Web
- Frontend
- Agents
- Curriculum
- Legacy modules

Architecture verification resulted in:

> **0 import violations**

This keeps the modules loosely coupled and makes them easier to test, maintain, and integrate.

---

## 27. COMPLETE END-TO-END WORKFLOW

The complete system can be summarized as:

```text
┌──────────────────────┐
│     TEACHER SETUP    │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ CONCEPT EXTRACTION   │
│ & VALIDATION         │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ TEACHER CONFIRMATION │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ TEST GENERATION      │
│ 3 MCQs / 4 options   │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│    STUDENT ATTEMPT   │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│      DIAGNOSIS       │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│      TAILORING       │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│        REVIEW        │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│      NOTE SAVING     │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│      ANALYTICS       │
│                      │
│ • Mastery            │
│ • Trends             │
│ • Aggregation        │
│ • Concept Graph      │
│ • Learning Path      │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ CLASS ANALYTICS      │
│ & CONCEPT GRAPH      │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│     FASTAPI / WEB    │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ TEACHER / STUDENT UI │
└──────────────────────┘
```

---

## 28. KEY TECHNICAL FEATURES

The completed workflow incorporates:

- AI-assisted curriculum extraction
- Concept validation and prerequisite checking
- Teacher-in-the-loop confirmation
- Diagnostic MCQ generation
- Structured student diagnosis
- Personalized learning/tailoring
- Human review and callbacks
- Versioned student notes
- Mastery calculation
- Learning trend analysis
- Class-level aggregation
- Student concept graphs
- Prerequisite traversal
- Topological learning paths
- Cycle detection
- State-machine orchestration
- Persistent workflow state
- Per-run locking
- JWT authentication
- Teacher/student RBAC
- FastAPI backend
- React frontend
- Deterministic testing
- Fixtures and stubs
- Architecture/import validation

---

## 29. FINAL SYSTEM OUTCOME

The completed Synapse workflow transforms raw educational material and student responses into a continuous adaptive learning cycle:

```text
TEACH
  ↓
UNDERSTAND CONCEPTS
  ↓
TEST
  ↓
MEASURE
  ↓
DIAGNOSE
  ↓
PERSONALIZE
  ↓
REVIEW
  ↓
ANALYSE
  ↓
LEARN
  ↓
REPEAT
```

Rather than treating assessment as a one-time activity, the system creates a feedback loop where student performance influences diagnosis, diagnosis influences personalized learning, and the resulting learning information is fed back into analytics and future learning cycles.

The architecture is modular and contract-driven, allowing curriculum generation, diagnosis, tailoring, analytics, runtime, API, and frontend components to operate as separate but interoperable modules.

---

## 30. FINAL VERIFICATION SUMMARY

| Area | Status |
| :--- | :--- |
| Shared Contracts | **Implemented** |
| Curriculum & Test Generation | **Implemented** |
| Concept Validation | **Implemented** |
| Teacher Confirmation | **Implemented** |
| Diagnostic Test Generation | **Implemented** |
| Student Workflow | **Implemented** |
| Diagnosis Pipeline | **Implemented** |
| Tailoring / Review | **Implemented** |
| Analytics | **Implemented** |
| Concept Graph | **Implemented** |
| Runtime / State Machine | **Implemented** |
| FastAPI Backend | **Implemented** |
| Authentication & RBAC | **Implemented** |
| React Frontend | **Implemented** |
| Deterministic Stubs & Fixtures | **Implemented** |
| Unit / Integration Testing | **Implemented** |
| Architecture Boundary Checks | **Verified** |

---

## 31. CONCLUSION

Synapse Cycle provides a complete AI-assisted adaptive learning workflow that connects teacher-provided curriculum, concept extraction, diagnostic assessment, student diagnosis, personalized learning, human review, analytics, and frontend interaction into a single state-driven pipeline.

The system is designed around modular architecture and shared contracts, allowing each component to remain independently testable while still participating in the complete learning cycle.

The use of deterministic stubs, fixtures, validation, bounded retries, state-machine control, persistence, authentication, and automated testing improves the reliability of the overall system.

The final workflow enables continuous learning:

```text
Teacher Setup
      ↓
Curriculum
      ↓
Assessment
      ↓
Student Response
      ↓
Diagnosis
      ↓
Personalization
      ↓
Analytics
      ↓
Feedback
      ↓
Next Learning Cycle
```

This creates a continuous adaptive learning loop rather than a one-time assessment system.