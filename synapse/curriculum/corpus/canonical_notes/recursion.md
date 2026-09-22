# Recursion

Recursion is a programming technique where a function solves a problem by calling a copy of itself with a smaller input.

## Key Principles
1. **Base Case**: Every recursive function must define a terminating base case that handles the simplest input directly without recursing further. Lacking a base case causes stack overflow.
2. **Recursive Step**: The inductive step that reduces the problem size towards the base case and invokes the function again.
3. **Call Stack**: Each recursive invocation pushes a stack frame containing local variables and return addresses until the base case returns.
