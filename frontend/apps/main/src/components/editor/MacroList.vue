<!-- Dropdown list for the "/" canned-reply picker. Modelled on MentionList.vue:
     same keyboard handling (up/down/enter, Escape is handled by the suggestion
     renderer) and the same popup positioning. Each row shows the macro name and
     whether it inserts reply text, runs actions, or both. -->
<template>
  <div
    v-if="items.length > 0"
    class="mention-list bg-background border rounded-lg shadow-lg overflow-hidden max-h-60 overflow-y-auto"
  >
    <button
      v-for="(item, index) in items"
      :key="item.id"
      class="mention-item w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-muted"
      :class="{ 'bg-muted': index === selectedIndex }"
      @click="selectItem(index)"
    >
      <span class="text-lg">💬</span>
      <span class="flex-1 truncate">{{ item.label }}</span>
      <span class="text-xs text-muted-foreground">{{ getHint(item) }}</span>
    </button>
  </div>
  <div v-else-if="query" class="mention-list bg-background border rounded-lg shadow-lg p-3">
    <span class="text-sm text-muted-foreground">{{ $t('globals.messages.noResultsFound') }}</span>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  command: {
    type: Function,
    required: true
  },
  query: {
    type: String,
    default: ''
  }
})

const selectedIndex = ref(0)

const getHint = (item) => {
  const parts = []
  if (item.has_message_content) parts.push(t('globals.terms.reply'))
  if (item.actions?.length) parts.push(t('globals.terms.action', item.actions.length))
  return parts.join(' · ')
}

const selectItem = (index) => {
  const item = props.items[index]
  if (item) {
    props.command({ id: item.id, label: item.label, has_message_content: item.has_message_content, actions: item.actions })
  }
}

const upHandler = () => {
  selectedIndex.value = (selectedIndex.value + props.items.length - 1) % props.items.length
}

const downHandler = () => {
  selectedIndex.value = (selectedIndex.value + 1) % props.items.length
}

const enterHandler = () => {
  selectItem(selectedIndex.value)
}

watch(
  () => props.items,
  () => {
    selectedIndex.value = 0
  }
)

// Scroll selected item into view on keyboard navigation
watch(selectedIndex, () => {
  nextTick(() => {
    document.querySelector('.mention-item.bg-muted')?.scrollIntoView({ block: 'nearest' })
  })
})

defineExpose({
  onKeyDown: ({ event }) => {
    if (event.key === 'ArrowUp') {
      upHandler()
      return true
    }
    if (event.key === 'ArrowDown') {
      downHandler()
      return true
    }
    if (event.key === 'Enter') {
      enterHandler()
      return true
    }
    return false
  }
})
</script>

<style scoped>
.mention-list {
  min-width: 240px;
}
</style>
