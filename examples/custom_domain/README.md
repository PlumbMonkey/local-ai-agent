"""Template for creating custom domains."""

"""
Custom Domain Template

Copy this directory to domains/{your_domain}/ and implement:
1. __init__.py - Public API
2. server.py - MCP server implementation  
3. tools.py - Domain-specific utilities

Example:

```python
# server.py
from core.mcp.server import MCPServer

class MyDomainServer(MCPServer):
    def __init__(self):
        super().__init__("my_domain")
        self.register_tool(...)
```
"""
