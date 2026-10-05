"""Shopping Agent — Smart shopping with real database integration and Amazon store connection."""

from datetime import datetime
from memory.knowledge_graph import KnowledgeGraph
import database as db


class ShoppingAgent:
    """Manages smart shopping with real purchase history from the database."""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    async def handle(self, message: str, entities: dict, session_id: str) -> dict:
        msg = message.lower()

        if any(w in msg for w in ["out of", "need more", "reorder", "buy more"]):
            item_name = self._extract_item(message)
            items = db.get_shopping_list(session_id)
            match = None
            for i in items:
                if any(w in i["product_name"].lower() for w in item_name.lower().split()):
                    match = i
                    break

            if match:
                return {
                    "text": f"🛒 I see you usually buy **{match['product_name']}** — estimated at ${match['estimated_price']:.2f}.\n\n{'🔄 Auto-reorder is enabled' if match['is_auto_reorder'] else '💡 Want me to set up automatic reordering?'}\n\n🔗 [View on Amazon]({match.get('amazon_url', '#')})",
                    "type": "smart_reorder",
                    "cards": [{
                        "type": "shopping_card",
                        "title": f"🛒 {match['product_name']}",
                        "body": f"${match['estimated_price']:.2f} • Same-day delivery available",
                        "actions": [
                            {"label": "🛒 Add to Cart", "value": "add_to_cart"},
                            {"label": "🔄 Set Auto-Reorder", "value": "set_recurring"},
                            {"label": "🔗 View on Amazon", "value": match.get("amazon_url", "#")},
                        ],
                    }],
                }
            else:
                return {
                    "text": f"🛒 I'll help you find **{item_name}**. Let me search for the best options with same-day delivery.",
                    "type": "search",
                    "cards": [],
                }

        elif any(w in msg for w in ["suggest", "need anything", "shopping list", "what do i need"]):
            return await self.get_suggestions_response(session_id)

        elif any(w in msg for w in ["add", "put"]):
            item_name = self._extract_item(message)
            db.add_shopping_item(session_id, {
                "product_name": item_name,
                "category": "general",
                "quantity": 1,
                "estimated_price": 0,
            })
            return {
                "text": f"🛒 Added **{item_name}** to your shopping list!",
                "type": "item_added",
                "cards": [],
            }

        return await self.get_suggestions_response(session_id)

    async def get_suggestions(self, session_id: str) -> dict:
        """Get reorder suggestions based on real purchase data."""
        items = db.get_shopping_list(session_id)
        auto_reorder = [i["product_name"] for i in items if i.get("is_auto_reorder")]
        return {
            "reorder_suggestions": auto_reorder[:3] if auto_reorder else [i["product_name"] for i in items[:3]],
        }

    async def get_suggestions_response(self, session_id: str) -> dict:
        items = db.get_shopping_list(session_id)

        if not items:
            return {
                "text": "🛒 Your shopping list is empty! Tell me what you need and I'll track it.",
                "type": "shopping",
                "cards": [],
            }

        text = "🛒 Your shopping list:\n\n"
        total = 0.0
        for i in items:
            status = "✅" if i.get("is_purchased") else "⬜"
            price = i.get("estimated_price", 0) or 0
            total += price * (i.get("quantity", 1))
            auto = " 🔄" if i.get("is_auto_reorder") else ""
            text += f"{status} **{i['product_name']}** — ${price:.2f} x{i.get('quantity', 1)}{auto}\n"
            if i.get("amazon_url"):
                text += f"   🔗 [View on Amazon]({i['amazon_url']})\n"

        text += f"\n💰 Estimated total: **${total:.2f}**"

        return {
            "text": text,
            "type": "shopping_list",
            "cards": [{
                "type": "shopping_card",
                "title": f"🛒 Shopping List ({len(items)} items)",
                "body": f"Estimated total: ${total:.2f}",
                "actions": [
                    {"label": "🛒 Order All on Amazon", "value": "order_all"},
                    {"label": "📋 Clear Purchased", "value": "clear_purchased"},
                ],
            }],
        }

    def _extract_item(self, message: str) -> str:
        msg = message.lower()
        for word in ["out of", "need more", "buy", "order", "reorder", "add", "put"]:
            if word in msg:
                return msg.split(word)[-1].strip().rstrip(".")
        return message
