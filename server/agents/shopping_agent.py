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

        if "track" in msg:
            return {
                "text": "Sure! I'm pulling up your active orders and tracking information.",
                "type": "amazon_tracking",
                "cards": [{
                    "type": "action_card",
                    "title": "📍 Track Orders",
                    "body": "View the live status of your Amazon shipments.",
                    "actions": [{"label": "Open Tracking", "value": "open_tracking"}]
                }]
            }

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

        elif any(w in msg for w in ["groceries", "ingredients", "meal plan", "fresh", "diet"]):
            return {
                "text": "🛒 I can help you shop for groceries on Amazon Fresh! What specific items do you need?",
                "type": "amazon_fresh",
                "cards": []
            }

        elif any(w in msg for w in ["checkout", "place order", "buy it", "confirm"]):
            items = db.get_shopping_list(session_id)
            if not items:
                return {
                    "text": "Your cart is currently empty! Add items first before checking out.",
                    "type": "amazon_checkout",
                    "cards": [],
                }
            
            # Real checkout simulation: convert shopping items to orders
            total = sum((i.get("estimated_price", 0) or 0) * i.get("quantity", 1) for i in items)
            
            order_ids = []
            for i in items:
                # Add to orders table
                order_result = db.add_order(session_id, {
                    "product_name": i["product_name"],
                    "amazon_url": i.get("amazon_url", ""),
                    "quantity": i.get("quantity", 1),
                    "total_price": (i.get("estimated_price", 0) or 0) * i.get("quantity", 1)
                })
                order_ids.append(order_result["tracking_id"])
                
                # Remove from shopping list since it's purchased
                db.delete_shopping_item(i["id"])
                
            from datetime import datetime, timedelta
            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            start_time = now + timedelta(hours=2)
            end_time = now + timedelta(hours=4)
            start_str = start_time.strftime("%I:%M %p").lstrip("0")
            end_str = end_time.strftime("%I:%M %p").lstrip("0")
                
            return {
                "text": f"🎉 **Order Placed Successfully!**\n\nYour Amazon Fresh delivery for {len(items)} items (${total:.2f}) has been confirmed. Tracking IDs generated.",
                "type": "amazon_checkout",
                "cards": [{
                    "type": "info_card",
                    "title": "📦 Delivery Scheduled",
                    "body": f"Total Charged: **${total:.2f}**\nExpected Delivery: Today, {start_str} - {end_str}\n\nCheck the **Tracking** tab to see your live order status.",
                    "actions": [
                        {"label": "📍 Track Orders", "value": "open_tracking"}
                    ]
                }]
            }

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
            
            # Generate real search URL if missing or generic
            url = i.get("amazon_url")
            if not url or url == "https://amazon.com":
                import urllib.parse
                url = "https://www.amazon.com/s?k=" + urllib.parse.quote(i['product_name'])
                
            text += f"   🔗 [View on Amazon]({url})\n"

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
