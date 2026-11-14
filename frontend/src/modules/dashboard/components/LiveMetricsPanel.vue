<script setup lang="ts">
/** Live CPU / memory / disk / network cards and top processes (§9.2). */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import EChart from '@/components/charts/EChart.vue'
import { useLiveMetrics } from '@/composables/useLiveMetrics'
import { formatBytes } from '@/utils/format'

const { t } = useI18n()
const { current, recent, error } = useLiveMetrics()

const pct = (used: number, total: number) => (total > 0 ? Math.round((used / total) * 100) : 0)
const rate = (bps: number) => `${formatBytes(Math.round(bps), t)}/s`
const barClass = (p: number) => (p >= 90 ? 'bg-danger' : p >= 75 ? 'bg-warning' : 'bg-primary')

const sparkline = computed(() => ({
  grid: { left: 0, right: 0, top: 4, bottom: 0 },
  xAxis: { type: 'category', show: false, data: recent.value.map((m) => m.timestamp) },
  yAxis: { type: 'value', show: false, min: 0, max: 100 },
  series: [
    {
      type: 'line',
      data: recent.value.map((m) => Math.round(m.cpu_percent)),
      smooth: true,
      symbol: 'none',
      areaStyle: { opacity: 0.15 },
    },
  ],
  animation: false,
}))
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-warning">{{ t('dashboard.agent_unavailable') }}</div>
    <div class="row g-3">
      <div class="col-6 col-lg-3">
        <div class="card h-100">
          <div class="card-body">
            <div class="text-body-secondary small">{{ t('monitoring.cpu') }}</div>
            <div class="fs-4 fw-semibold">
              {{ current ? Math.round(current.cpu_percent) : '—' }}%
            </div>
            <EChart :option="sparkline" height="40px" />
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card h-100">
          <div class="card-body">
            <div class="text-body-secondary small">{{ t('monitoring.load') }}</div>
            <div class="fs-4 fw-semibold ltr-island">
              {{ current ? current.load1.toFixed(2) : '—' }}
            </div>
            <div v-if="current" class="small text-body-secondary ltr-island">
              {{ current.load5.toFixed(2) }} · {{ current.load15.toFixed(2) }}
            </div>
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card h-100">
          <div class="card-body">
            <div class="text-body-secondary small">{{ t('monitoring.memory') }}</div>
            <template v-if="current">
              <div class="fs-4 fw-semibold">
                {{ pct(current.memory_used, current.memory_total) }}%
              </div>
              <div class="progress mb-1" style="height: 0.35rem">
                <div
                  class="progress-bar"
                  :class="barClass(pct(current.memory_used, current.memory_total))"
                  :style="{ width: `${pct(current.memory_used, current.memory_total)}%` }"
                ></div>
              </div>
              <div class="small text-body-secondary">
                {{ formatBytes(current.memory_used, t) }} /
                {{ formatBytes(current.memory_total, t) }}
              </div>
              <div v-if="current.swap_total" class="small text-body-secondary">
                {{ t('monitoring.swap') }}: {{ formatBytes(current.swap_used, t) }}
              </div>
            </template>
            <div v-else class="ed-skeleton"></div>
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="card h-100">
          <div class="card-body">
            <div class="text-body-secondary small">{{ t('monitoring.network') }}</div>
            <template v-if="current">
              <div>
                <i class="bi bi-arrow-down text-success"></i> {{ rate(current.net_rx_bps) }}
              </div>
              <div><i class="bi bi-arrow-up text-primary"></i> {{ rate(current.net_tx_bps) }}</div>
              <div class="text-body-secondary small mt-1">{{ t('monitoring.disk_io') }}</div>
              <div class="small">
                {{ t('monitoring.read') }} {{ rate(current.disk_read_bps) }} ·
                {{ t('monitoring.write') }} {{ rate(current.disk_write_bps) }}
              </div>
            </template>
            <div v-else class="ed-skeleton"></div>
          </div>
        </div>
      </div>

      <div class="col-12 col-xl-6">
        <div class="card h-100">
          <div class="card-header fw-semibold">{{ t('monitoring.disks') }}</div>
          <ul class="list-group list-group-flush">
            <li v-for="d in current?.disks ?? []" :key="d.mountpoint" class="list-group-item">
              <div class="d-flex justify-content-between small">
                <code>{{ d.mountpoint }}</code>
                <span>{{ formatBytes(d.used, t) }} / {{ formatBytes(d.total, t) }}</span>
              </div>
              <div class="progress mt-1" style="height: 0.35rem">
                <div
                  class="progress-bar"
                  :class="barClass(d.percent)"
                  :style="{ width: `${d.percent}%` }"
                ></div>
              </div>
            </li>
          </ul>
        </div>
      </div>
      <div class="col-12 col-xl-6">
        <div class="card h-100">
          <div class="card-header fw-semibold">{{ t('monitoring.top_processes') }}</div>
          <div class="table-responsive">
            <table class="table table-sm mb-0 align-middle">
              <thead>
                <tr>
                  <th>{{ t('monitoring.process') }}</th>
                  <th>{{ t('monitoring.user') }}</th>
                  <th class="text-end">{{ t('monitoring.cpu') }}</th>
                  <th class="text-end">{{ t('monitoring.memory') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in current?.top_cpu ?? []" :key="p.pid">
                  <td class="ltr-island">
                    {{ p.name }} <small class="text-body-secondary">{{ p.pid }}</small>
                  </td>
                  <td class="ltr-island">{{ p.username }}</td>
                  <td class="text-end">{{ p.cpu_percent.toFixed(1) }}%</td>
                  <td class="text-end">{{ formatBytes(p.memory_rss, t) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
