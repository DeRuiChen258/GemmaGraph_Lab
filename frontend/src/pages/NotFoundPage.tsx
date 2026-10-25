import { Link } from 'react-router-dom'
import { CircleHelp } from 'lucide-react'
import { EmptyState, PageHeading, Panel } from '@/components/ui'

export default function NotFoundPage() {
  return <><PageHeading eyebrow="404" title="页面不存在" /><Panel><EmptyState icon={CircleHelp} title="找不到这个页面" description="地址可能已经变化，或者链接不完整。"
    action={<Link className="button button-primary button-sm" to="/overview">返回概览</Link>} /></Panel></>
}
