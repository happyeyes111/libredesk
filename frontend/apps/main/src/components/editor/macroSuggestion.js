// Slash (/) canned-reply picker (Phase 3, Chatwoot-style).
// Mirrors mentionSuggestion.js but triggers on "/" and lists macros instead of
// people. Selecting a macro does NOT insert a mention node: the command
// deletes the typed "/query" trigger and asks the host (ReplyBoxContent) for
// the macro's reply text, which it inserts at the cursor. The host also
// records the macro's actions on the conversation, exactly like the macro
// palette picker does — but without message_content, so ReplyBox's watcher
// does not replace the whole draft with the macro text.
import MacroList from './MacroList.vue'
import { createSuggestionRenderer } from './suggestionRenderer'

export default {
  char: '/',
  allowSpaces: true,
  allow: ({ editor }) => editor.options.editorProps?.enableMacroSuggestions?.() ?? false,
  items: ({ query, editor }) => editor.options.editorProps?.getMacroSuggestions?.(query) ?? [],
  command: async ({ editor, range, props }) => {
    editor.chain().focus().deleteRange(range).run()
    const content = await editor.options.editorProps?.onMacroSelected?.(props)
    if (content) editor.chain().focus().insertContent(content).run()
  },
  render: () => createSuggestionRenderer(MacroList)
}
