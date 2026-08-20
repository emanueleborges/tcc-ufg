/** Utilitários de exportação (CSV e gráfico PNG) para o TCC. */

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function exportReadingTimesCsv(
  items: Array<{
    lawyer_name: string
    minutes: number
    label: string
    created_at: string
  }>,
  summary: {
    mean_label: string | null
    prototype_mean_label: string
    speedup_factor: number | null
  },
): void {
  const rows = [
    'advogado;tempo;minutos;data',
    ...[...items]
      .reverse()
      .map((item) => {
        const date = new Date(item.created_at).toLocaleDateString('pt-BR')
        const name = item.lawyer_name.replace(/;/g, ',')
        return `${name};${item.label};${item.minutes};${date}`
      }),
  ]
  if (summary.mean_label) {
    rows.push(`média humana;${summary.mean_label};;`)
  }
  rows.push(`média aplicação;${summary.prototype_mean_label};;`)
  if (summary.speedup_factor != null) {
    rows.push(`ganho de velocidade;${summary.speedup_factor}x;;`)
  }
  const blob = new Blob([`${rows.join('\n')}\n`], {
    type: 'text/csv;charset=utf-8',
  })
  downloadBlob('tempos_leitura_advogados.csv', blob)
}

function resolveCssColor(value: string, fallback: string): string {
  if (!value.startsWith('var(')) return value || fallback
  const match = /var\((--[\w-]+)(?:,\s*([^)]+))?\)/.exec(value)
  if (!match) return fallback
  const resolved = getComputedStyle(document.documentElement)
    .getPropertyValue(match[1])
    .trim()
  return resolved || match[2]?.trim() || fallback
}

export async function exportChartPng(
  svg: SVGSVGElement,
  filename = 'grafico_tempos_leitura.png',
): Promise<void> {
  const clone = svg.cloneNode(true) as SVGSVGElement
  const width = Number(svg.getAttribute('width') || 760)
  const height = Number(svg.getAttribute('height') || 260)

  clone.querySelectorAll('[class]').forEach((node) => {
    const el = node as SVGElement
    const className = el.getAttribute('class') || ''
    const style = getComputedStyle(el)
    const accent =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--accent')
        .trim() || '#6fbf9a'
    const warn =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--warn')
        .trim() || '#e0a070'
    const ink =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--ink')
        .trim() || '#e8efe9'
    const muted =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--muted')
        .trim() || '#9eb0a6'
    const panel =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--assistant-bg')
        .trim() || '#1a2420'

    if (el.tagName === 'rect') {
      el.setAttribute('fill', panel)
    }
    if (el.tagName === 'path') {
      if (className.includes('pie-slice-human')) el.setAttribute('fill', warn)
      else if (className.includes('pie-slice-proto')) el.setAttribute('fill', accent)
      else el.setAttribute('fill', resolveCssColor(style.fill, accent))
    }
    if (el.tagName === 'line' || el.tagName === 'polyline') {
      const stroke = className.includes('chart-proto-line')
        ? accent
        : className.includes('chart-mean-line')
          ? warn
          : resolveCssColor(style.stroke, accent)
      el.setAttribute('stroke', stroke)
      el.setAttribute('stroke-width', style.strokeWidth || '2')
      if (style.strokeDasharray && style.strokeDasharray !== 'none') {
        el.setAttribute('stroke-dasharray', style.strokeDasharray)
      }
      if (el.tagName === 'polyline') {
        el.setAttribute('fill', 'none')
        el.setAttribute('stroke-linejoin', 'round')
        el.setAttribute('stroke-linecap', 'round')
      }
    }
    if (el.tagName === 'circle') {
      if (className.includes('pie-hole')) {
        el.setAttribute('fill', panel)
        el.removeAttribute('stroke')
      } else {
        el.setAttribute('fill', panel)
        el.setAttribute('stroke', accent)
        el.setAttribute('stroke-width', style.strokeWidth || '2')
      }
    }
    if (el.tagName === 'text') {
      const fill = className.includes('pie-center-value')
        ? ink
        : className.includes('chart-proto-label')
          ? accent
          : className.includes('chart-mean-label')
            ? warn
            : muted
      el.setAttribute('fill', fill)
      el.setAttribute('font-size', style.fontSize || '11px')
      el.setAttribute('font-family', style.fontFamily || 'sans-serif')
      if (className.includes('pie-center') || className.includes('chart-x-label')) {
        el.setAttribute('text-anchor', 'middle')
      } else if (className.includes('chart-mean-label')) {
        el.setAttribute('text-anchor', 'end')
      } else if (className.includes('chart-y-label')) {
        el.setAttribute('text-anchor', 'end')
      } else if (className.includes('chart-proto-label')) {
        el.setAttribute('text-anchor', 'start')
      }
      if (style.fontWeight) {
        el.setAttribute('font-weight', style.fontWeight)
      }
    }
    el.removeAttribute('class')
  })

  const bg =
    getComputedStyle(document.documentElement)
      .getPropertyValue('--assistant-bg')
      .trim() || '#1a2420'
  const bgRect = clone.querySelector('rect')
  if (bgRect) bgRect.setAttribute('fill', bg)

  const serializer = new XMLSerializer()
  const svgText = serializer.serializeToString(clone)
  const svgBlob = new Blob([svgText], {
    type: 'image/svg+xml;charset=utf-8',
  })
  const url = URL.createObjectURL(svgBlob)

  await new Promise<void>((resolve, reject) => {
    const image = new Image()
    image.onload = () => {
      const scale = 2
      const canvas = document.createElement('canvas')
      canvas.width = width * scale
      canvas.height = height * scale
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        URL.revokeObjectURL(url)
        reject(new Error('Canvas indisponível.'))
        return
      }
      ctx.scale(scale, scale)
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, width, height)
      ctx.drawImage(image, 0, 0, width, height)
      URL.revokeObjectURL(url)
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error('Falha ao gerar PNG.'))
          return
        }
        downloadBlob(filename, blob)
        resolve()
      }, 'image/png')
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Falha ao renderizar o gráfico.'))
    }
    image.src = url
  })
}
