/* 地区显示口径：底层数据存六值（中国/日本/韩国/欧洲/美国/其他，按第一制片国判定），
   旧值（华语/欧美）仅做兼容映射。复合词「欧美」由后端 region_match 展开为欧洲+美国。 */
export const REGION_LABEL: Record<string, string> = {
  中国: '中国',
  日本: '日本',
  韩国: '韩国',
  欧洲: '欧洲',
  美国: '美国',
  其他: '其他',
  华语: '中国',
  欧美: '欧美',
}

export function regionLabel(r?: string | null): string {
  if (!r) return ''
  return REGION_LABEL[r] || r
}
