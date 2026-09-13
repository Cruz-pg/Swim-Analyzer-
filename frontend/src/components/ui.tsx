import { useId, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X, ChevronDown } from 'lucide-react'

export function Modal({ open, onClose, title, description, children, wide = false }: {
  open: boolean; onClose: () => void; title: string; description: string; children: ReactNode; wide?: boolean
}) {
  return <Dialog.Root open={open} onOpenChange={value => { if (!value) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="modal-overlay" />
      <Dialog.Content className={`modal ${wide ? 'modal-wide' : ''}`}>
        <div className="modal-heading">
          <div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div>
          <Dialog.Close className="icon-button" aria-label="Close dialog"><X size={20} /></Dialog.Close>
        </div>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export function Select({ value, onChange, options, disabled, label }: {
  value: string; onChange: (value: string) => void; options: string[]; disabled?: boolean; label?: string
}) {
  return <span className="select-wrap"><select aria-label={label} value={value} onChange={event => onChange(event.target.value)} disabled={disabled}>
    {options.map(option => <option key={option} value={option}>{option}</option>)}
  </select><ChevronDown size={15} aria-hidden="true" /></span>
}

export function Toggle({ label, detail, checked, onChange }: {
  label: string; detail: string; checked: boolean; onChange: (checked: boolean) => void
}) {
  const id = useId()
  return <label className="toggle-row" htmlFor={id}><span><strong>{label}</strong><small>{detail}</small></span>
    <input className="switch-input" id={id} type="checkbox" role="switch" checked={checked} onChange={event => onChange(event.target.checked)} />
    <span className="switch-track" aria-hidden="true"><span /></span>
  </label>
}
