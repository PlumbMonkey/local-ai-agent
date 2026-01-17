"""Mock data generator for testing and development."""

import json
from datetime import datetime, timedelta
from typing import List
from uuid import uuid4


class ConversationGenerator:
    """Generate realistic mock conversations across domains."""

    CODING_CONVERSATIONS = [
        {
            "user": "How do I handle async timeouts in Python?",
            "assistant": "Use asyncio.wait_for() with a timeout parameter. Here's an example:\n\n```python\nimport asyncio\n\nasync def fetch_with_timeout():\n    try:\n        result = await asyncio.wait_for(\n            fetch_data(),\n            timeout=5.0\n        )\n    except asyncio.TimeoutError:\n        print('Request timed out')\n```",
            "tags": ["python", "async", "timeout", "asyncio"]
        },
        {
            "user": "What's the difference between list and tuple in Python?",
            "assistant": "Lists are mutable, tuples are immutable. Lists use square brackets [], tuples use parentheses (). Tuples are hashable and can be used as dict keys.",
            "tags": ["python", "data-structures"]
        },
        {
            "user": "How do I optimize database queries?",
            "assistant": "Use indexing, query caching, batch operations, and avoid N+1 queries. Consider using query profiling tools to identify bottlenecks.",
            "tags": ["database", "performance", "sql"]
        }
    ]

    MUSIC_CONVERSATIONS = [
        {
            "user": "What's a good chord progression for lo-fi hip hop?",
            "assistant": "Try: Dm7 - G7 - Cmaj7 - Fmaj7. This is a classic lo-fi progression that sounds smooth and jazzy. You can loop it for 8 or 16 bars.",
            "tags": ["music", "chords", "lofi", "hip-hop"]
        },
        {
            "user": "How do I layer drums in my mix?",
            "assistant": "Layer a sub-bass kick (20-60Hz) with a punchy kick (200-300Hz). Use sidechain compression on the bass to avoid mud. Add a click or 808 for character.",
            "tags": ["music", "mixing", "drums", "production"]
        },
        {
            "user": "What's the best way to EQ vocals?",
            "assistant": "High-pass filter below 80Hz, cut harshness around 3-5kHz, boost presence at 4-8kHz, and add air above 10kHz. Use a gentle bell curve, not aggressive cuts.",
            "tags": ["music", "mixing", "vocals", "eq"]
        }
    ]

    BLENDER_CONVERSATIONS = [
        {
            "user": "How do I create a realistic metal material?",
            "assistant": "Use Principled BSDF with Metallic: 1.0, Roughness: 0.2-0.4, and add a slight ColorRamp for imperfections. Use Ambient Occlusion texture for wear.",
            "tags": ["blender", "materials", "rendering", "pbr"]
        },
        {
            "user": "Why is my render so slow?",
            "assistant": "Check for: High poly count (use decimation), subsurface scattering enabled unnecessarily, complex node trees. Try adaptive sampling or denoise.",
            "tags": ["blender", "rendering", "performance", "optimization"]
        },
        {
            "user": "How do I rig a character efficiently?",
            "assistant": "Use Bendy Bones for secondary rigging, parent bones correctly, use constraints sparingly. Keep bone count low (<150 for game characters).",
            "tags": ["blender", "rigging", "animation", "characters"]
        }
    ]

    STUDY_CONVERSATIONS = [
        {
            "user": "What are the key concepts in machine learning?",
            "assistant": "Supervised learning (regression, classification), unsupervised learning (clustering, dimensionality reduction), and reinforcement learning. Start with linear regression.",
            "tags": ["ml", "ai", "learning", "study"]
        },
        {
            "user": "Explain gradient descent",
            "assistant": "An optimization algorithm that iteratively adjusts weights to minimize loss. Works by computing gradients (partial derivatives) and moving in the direction of steepest descent.",
            "tags": ["ml", "math", "optimization"]
        },
        {
            "user": "What's the difference between training and validation sets?",
            "assistant": "Training set trains the model, validation set tunes hyperparameters, test set evaluates final performance. Typical split: 70/15/15.",
            "tags": ["ml", "data-science", "methodology"]
        }
    ]

    GENERAL_CONVERSATIONS = [
        {
            "user": "What's a good productivity technique?",
            "assistant": "The Pomodoro Technique: 25 min focused work, 5 min break. Repeat 4 times, then take a longer 15-30 min break.",
            "tags": ["productivity", "time-management"]
        },
        {
            "user": "How do I stay motivated on long projects?",
            "assistant": "Break projects into smaller milestones, celebrate small wins, track progress visually, and find accountability partners.",
            "tags": ["productivity", "motivation", "mindset"]
        }
    ]

    @staticmethod
    def generate_mock_conversations(
        count: int = 100,
        domains: List[str] = None,
    ) -> List[dict]:
        """
        Generate realistic mock conversations.

        Args:
            count: Total conversations to generate
            domains: Domains to include (default: all)

        Returns:
            List of conversation dicts ready for ingestion
        """
        if domains is None:
            domains = ["coding", "music", "blender", "study", "general"]

        conversations = []
        now = datetime.now()

        domain_map = {
            "coding": ConversationGenerator.CODING_CONVERSATIONS,
            "music": ConversationGenerator.MUSIC_CONVERSATIONS,
            "blender": ConversationGenerator.BLENDER_CONVERSATIONS,
            "study": ConversationGenerator.STUDY_CONVERSATIONS,
            "general": ConversationGenerator.GENERAL_CONVERSATIONS,
        }

        for i in range(count):
            # Distribute evenly across domains
            domain = domains[i % len(domains)]
            template = domain_map[domain][i % len(domain_map[domain])]

            # Generate timestamp (spread over last 6 months)
            days_ago = i % 180
            timestamp = (now - timedelta(days=days_ago)).isoformat() + "Z"

            conversation = {
                "id": f"conv_{uuid4().hex[:8]}",
                "timestamp": timestamp,
                "participants": ["PlumbMonkey", "AI"],
                "domain": domain,
                "messages": [
                    {"role": "user", "content": template["user"]},
                    {"role": "assistant", "content": template["assistant"]},
                ],
                "tags": template["tags"],
            }

            conversations.append(conversation)

        return conversations


def generate_mock_conversations(
    count: int = 100,
    domains: List[str] = None,
) -> List[dict]:
    """Convenience function to generate mock conversations."""
    return ConversationGenerator.generate_mock_conversations(count, domains)


def save_mock_data_as_json(filepath: str, count: int = 1000) -> None:
    """Save mock conversations to a JSON file for testing."""
    conversations = generate_mock_conversations(count)
    data = {"conversations": conversations}

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Generated {count} mock conversations at {filepath}")


if __name__ == "__main__":
    # Generate and save mock data
    save_mock_data_as_json("examples/mock_chat_export.json", count=1000)
