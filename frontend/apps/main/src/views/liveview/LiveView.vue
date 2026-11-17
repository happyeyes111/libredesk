<!-- Live View (Phase 3): Chatwoot-style visitor monitoring, rebuilt for Libredesk.
     Lists the visitors currently browsing the user's websites — who they are,
     which site/inbox, the page they are on and how long they have been there —
     with a link straight into the visitor's open conversation. Polls every
     10s (paused while the tab is hidden); the time-on-site column ticks every
     second from each visitor's first_seen time. -->
<template>
  <div class="overflow-y-auto">
    <div class="p-4 md:p-6 w-full md:w-[calc(100%-3rem)]" :class="{ 'opacity-50 transition-opacity duration-300': isLoading && visitors.length === 0 }">
      <Spinner v-if="isLoading && visitors.length === 0" />

      <div class="space-y-6">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-700 dark:text-emerald-400">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
                <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              {{ $t('liveView.visitorsOnline') }}: {{ visitors.length }}
            </span>
            <span class="text-sm text-muted-foreground">{{ $t('liveView.subtitle') }}</span>
          </div>
          <Button size="sm" variant="outline" :disabled="isLoading" @click="fetchVisitors">
            {{ $t('globals.terms.refresh') }}
          </Button>
        </div>

        <div v-if="visitors.length === 0 && !isLoading" class="text-sm text-muted-foreground">
          {{ $t('liveView.noVisitors') }}
        </div>

        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>{{ $t('liveView.visitor') }}</TableHead>
              <TableHead>{{ $t('liveView.site') }}</TableHead>
              <TableHead>{{ $t('liveView.currentPage') }}</TableHead>
              <TableHead>{{ $t('liveView.timeOnSite') }}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="visitor in visitors" :key="visitor.contact_id">
              <TableCell>
                <div class="font-medium">{{ visitor.name }}</div>
                <div v-if="visitor.email" class="text-xs text-muted-foreground">{{ visitor.email }}</div>
              </TableCell>
              <TableCell>{{ visitor.inbox_name }}</TableCell>
              <TableCell class="max-w-xs">
                <a v-if="visitor.url" :href="visitor.url" target="_blank" rel="noopener" class="text-primary hover:underline truncate block">
                  {{ visitor.title || visitor.url }}
                </a>
                <span v-else class="text-muted-foreground">—</span>
              </TableCell>
              <TableCell>{{ formatDuration(secondsOnSite(visitor)) }}</TableCell>
              <TableCell>
                <router-link
                  v-if="visitor.conversation_uuid"
                  :to="{ name: 'inbox-conversation', params: { type: 'all', uuid: visitor.conversation_uuid } }"
                >
                  <Button size="sm" variant="outline">{{ $t('liveView.openChat') }}</Button>
                </router-link>
                <span v-else class="text-muted-foreground text-sm">—</span>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useIntervalFn, useDocumentVisibility } from '@vueuse/core'
import { useEmitter } from '@main/composables/useEmitter'
import { EMITTER_EVENTS } from '@main/constants/emitterEvents.js'
import { handleHTTPError } from '@shared-ui/utils/http.js'
import { formatDuration } from '@shared-ui/utils/datetime.js'
import Spinner from '@shared-ui/components/ui/spinner/Spinner.vue'
import { Button } from '@shared-ui/components/ui/button/index.js'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@shared-ui/components/ui/table'
import api from '@main/api'

const emitter = useEmitter()
const visitors = ref([])
const isLoading = ref(false)
// Ticks every second so the time-on-site column counts up live between polls.
const now = ref(Date.now())
const visibility = useDocumentVisibility()

const secondsOnSite = (visitor) => {
  const firstSeen = new Date(visitor.first_seen).getTime()
  if (!firstSeen) return visitor.seconds_on_site || 0
  return Math.max(0, Math.floor((now.value - firstSeen) / 1000))
}

const fetchVisitors = async () => {
  isLoading.value = true
  try {
    const { data } = await api.getLiveView()
    visitors.value = data.data || []
  } catch (error) {
    emitter.emit(EMITTER_EVENTS.SHOW_TOAST, {
      variant: 'destructive',
      description: handleHTTPError(error).message
    })
  } finally {
    isLoading.value = false
  }
}

const { pause: pausePoll, resume: resumePoll } = useIntervalFn(
  () => {
    if (visibility.value === 'visible') fetchVisitors()
  },
  10000,
  { immediate: false }
)
useIntervalFn(() => {
  now.value = Date.now()
}, 1000)

onMounted(() => {
  fetchVisitors()
  resumePoll()
})

onUnmounted(() => {
  pausePoll()
})
</script>
