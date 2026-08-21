import { useEffect, useRef } from 'react'
import type { EChartsOption } from 'echarts'

/* 按需加载 echarts 的极简封装：init / setOption / dispose */
export default function EChart({ option, height = 220, className }: {
  option: EChartsOption
  height?: number
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<{ dispose: () => void } | null>(null)

  useEffect(() => {
    let disposed = false
    void import('echarts').then((echarts) => {
      if (disposed || !ref.current) return
      const chart = echarts.init(ref.current)
      chartRef.current = chart
      chart.setOption(option)
    })
    return () => { disposed = true; chartRef.current?.dispose(); chartRef.current = null }
  }, [option])

  return <div ref={ref} style={{ height, width: '100%' }} className={className} />
}
