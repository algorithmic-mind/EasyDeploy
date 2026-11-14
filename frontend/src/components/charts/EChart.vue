<script setup lang="ts">
/** Minimal ECharts wrapper: tree-shaken line charts, resize-aware, follows the color mode. */
import { LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const props = withDefaults(defineProps<{ option: echarts.EChartsCoreOption; height?: string }>(), {
  height: '260px',
})

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null
let themeObserver: MutationObserver | null = null

function isDark(): boolean {
  return document.documentElement.getAttribute('data-bs-theme') === 'dark'
}

function render(): void {
  if (!el.value) return
  chart?.dispose()
  chart = echarts.init(el.value, isDark() ? 'dark' : undefined, { renderer: 'canvas' })
  chart.setOption({ backgroundColor: 'transparent', ...props.option })
}

onMounted(() => {
  render()
  if (el.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(el.value)
  }
  themeObserver = new MutationObserver(render)
  themeObserver.observe(document.documentElement, { attributeFilter: ['data-bs-theme'] })
})

watch(
  () => props.option,
  (option) => chart?.setOption(option, { notMerge: false, lazyUpdate: true }),
  { deep: true },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  themeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" dir="ltr" :style="{ height, width: '100%' }"></div>
</template>
