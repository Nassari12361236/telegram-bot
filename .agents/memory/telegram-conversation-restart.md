---
name: Telegram ConversationHandler restart
---

When a menu button (like "🛒 خرید اشتراک") starts a ConversationHandler, the same button should also be registered as a fallback inside that ConversationHandler. Otherwise, if the user presses the button again while already inside the conversation, the entry point is not re-triggered and the update falls through to the general unknown handler, producing a confusing message.

**Why:** ConversationHandler entry points only run when the user is *not* already in that conversation. To allow a restart from any state, add a matching MessageHandler to `fallbacks` that returns the first state again.
