<script setup lang="ts">
/** Host → Monitoring: history charts from monitor.db (1 h / 24 h / 7 d / 30 d). */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { monitoringApi, type HistoryPoint } from '@/api/client'
import EChart from '@/components/charts/EChart.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useApiError } from '@/composables/useApiError'
import { formatBytes } from '@/utils/format'

const RANGES = ['1h', '24h', '7d', '30d'] as const
type Range = (typeof RANGES)[number]

const { t } = useI18n()
const apiError = useApiError()
const range = ref<Range>('1h')
const points = ref<HistoryPoint[]>([])
const loading = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    points.value = (await monitoringApi.history(range.value)).points
  } catch (err) {
    error.value = apiError.message(err)
  } finally {
    loading.value = false
  }
}

const times = computed(() => points.value.map((p) => new Date(p.ts).toLocaleString()))

function chart(
  series: { name: string; values: number[] }[],
  yFormatter?: (v: number) => string,
  max?: number,
) {
  return {
    tooltip: { trigger: 'axis', valueFormatter: yFormatter },
    legend: { top: 0 },
    grid: { left: 60, right: 16, top: 32, bottom: 40 },
    xAxis: { type: 'category', data: times.value, boundaryGap: false },
    yAxis: { type: 'value', max, axisLabel: { formatter: yFormatter } },
    dataZoom: [{ type: 'inside' }],
    series: series.map((s) => ({
      name: s.name,
      type: 'line',
      showSymbol: false,
      smooth: true,
      areaStyle: { opacity: 0.08 },
      data: s.values,
    })),
  }
}

const bytesRate = (v: number) => `${formatBytes(Math.round(v), t)}/s`
const percent = (v: number) => `${Math.round(v)}%`

const cpuChart = computed(() =>
  chart(
    [
      { name: t('monitoring.cpu'), values: points.value.map((p) => p.cpu_percent) },
      {
        name: t('monitoring.memory'),
        values: points.value.map((p) => (p.mem_total ? (p.mem_used / p.mem_total) * 100 : 0)),
      },
      { name: t('monitoring.disk_usage'), values: points.value.map((p) => p.disk_percent) },
    ],
    percent,
    100,
  ),
)
const loadChart = computed(() =>
  chart([{ name: t('monitoring.load'), values: points.value.map((p) => p.load1) }]),
)
const netChart = computed(() =>
  chart(
    [
      { name: t('monitoring.received'), values: points.value.map((p) => p.net_rx_bps) },
      { name: t('monitoring.sent'), values: points.value.map((p) => p.net_tx_bps) },
    ],
    bytesRate,
  ),
)
const diskChart = computed(() =>
  chart(
    [
      { name: t('monitoring.read'), values: points.value.map((p) => p.disk_read_bps) },
      { name: t('monitoring.write'), values: points.value.map((p) => p.disk_write_bps) },
    ],
    bytesRate,
  ),
)

watch(range, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-4">
      <h1 class="h4 mb-0 flex-grow-1">{{ t('nav.host.monitoring') }}</h1>
      <div class="btn-group" role="group" :aria-label="t('monitoring.range')">
        <button
          v-for="r in RANGES"
          :key="r"
          type="button"
          class="btn btn-sm"
          :class="range === r ? 'btn-primary' : 'btn-outline-secondary'"
          @click="range = r"
        >
          {{ t(`monitoring.ranges.${r}`) }}
        </button>
      </div>
    </div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="!loading && points.length === 0" class="card">
      <EmptyState
        icon="bi-graph-up"
        :title="t('monitoring.no_data')"
        :text="t('monitoring.no_data_text')"
      />
    </div>
    <div v-else class="row g-3">
      <div class="col-12 col-xl-6">
        <div class="card">
          <div class="card-header fw-semibold">{{ t('monitoring.usage') }}</div>
          <div class="card-body"><EChart :option="cpuChart" /></div>
        </div>
      </div>
      <div class="col-12 col-xl-6">
        <div class="card">
          <div class="card-header fw-semibold">{{ t('monitoring.load') }}</div>
          <div class="card-body"><EChart :option="loadChart" /></div>
        </div>
      </div>
      <div class="col-12 col-xl-6">
        <div class="card">
          <div class="card-header fw-semibold">{{ t('monitoring.network') }}</div>
          <div class="card-body"><EChart :option="netChart" /></div>
        </div>
      </div>
      <div class="col-12 col-xl-6">
        <div class="card">
          <div class="card-header fw-semibold">{{ t('monitoring.disk_io') }}</div>
          <div class="card-body"><EChart :option="diskChart" /></div>
        </div>
      </div>
    </div>
  </div>
</template>
