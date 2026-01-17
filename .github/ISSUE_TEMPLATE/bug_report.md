"""GitHub issue template for bug reports."""

name: Bug Report
description: Report a bug to help us improve
title: "[BUG] "
labels: ["bug"]

body:
  - type: markdown
    attributes:
      value: |
        Thank you for reporting this bug!

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Clear description of the bug
      placeholder: What went wrong?
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior
      placeholder: |
        1. Go to '...'
        2. Click on '...'
        3. See error

  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What should happen
      placeholder: It should...

  - type: textarea
    id: logs
    attributes:
      label: Logs
      description: Any error logs or stack traces
      render: python

  - type: input
    id: python_version
    attributes:
      label: Python Version
      placeholder: "3.11.0"

  - type: input
    id: os
    attributes:
      label: Operating System
      placeholder: "Windows 11 / macOS 14 / Ubuntu 22.04"
