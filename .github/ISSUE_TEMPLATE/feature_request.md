"""GitHub issue template for feature requests."""

name: Feature Request
description: Suggest an idea or enhancement
title: "[FEATURE] "
labels: ["enhancement"]

body:
  - type: markdown
    attributes:
      value: |
        Thank you for suggesting an enhancement!

  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
      description: Describe the problem this feature would solve
      placeholder: I'm trying to... but currently...

  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How should this feature work?
      placeholder: The feature should...

  - type: textarea
    id: alternatives
    attributes:
      label: Alternative Solutions
      description: Other ways to solve this?

  - type: textarea
    id: additional
    attributes:
      label: Additional Context
      description: Any other context?
