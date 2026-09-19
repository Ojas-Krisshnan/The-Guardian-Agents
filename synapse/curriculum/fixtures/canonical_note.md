# Recursion and Base Cases

Recursion is a programming technique where a function solves a problem by calling itself with smaller sub-problems.

## Key Components

### 1. Base Case
Every recursive function must have at least one base case: a terminating condition that produces a result directly without making further recursive calls. Without a base case, recursion leads to a stack overflow.

### 2. Recursive Case
The recursive case reduces the problem toward the base case by invoking the function on smaller inputs.

### 3. Call Stack
Each recursive invocation creates a new stack frame storing local variables and the return address.
