import { reviewReasonLabel } from '@/lib/statementEngine'

/**
 * Review codes rendered as the plain-language wording table.
 * Reusable by the result banner, details panel and dashboard.
 */
export default function ReviewReasons({ codes, id }: { codes: string[]; id?: string }) {
  if (!codes.length) return null
  return (
    <ul id={id} className="mt-1.5 list-inside list-disc space-y-0.5 break-words text-[11px] text-amber-800">
      {codes.map((c) => (
        <li key={c}>{reviewReasonLabel(c)}</li>
      ))}
    </ul>
  )
}
