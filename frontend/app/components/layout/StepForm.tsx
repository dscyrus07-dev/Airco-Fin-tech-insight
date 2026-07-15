'use client'

import { useMemo, useState } from 'react'
import { Plus, X } from 'lucide-react'
import { UserDetails, BankName } from '@/types'
import { validateUserDetails } from '@/lib/validation'
import { SUPPORTED_BANK_OPTIONS } from '@/lib/banks'

interface StepFormProps {
  onSubmit: (details: UserDetails) => void
  initialDetails?: UserDetails
}

export default function StepForm({ onSubmit, initialDetails }: StepFormProps) {
  const [details, setDetails] = useState<UserDetails>(
    initialDetails || {
      fullName: '',
      accountType: '',
      bankName: '',
      selectedBanks: [],
    }
  )
  const [bankToAdd, setBankToAdd] = useState<BankName | ''>('')
  const [error, setError] = useState<string | null>(null)

  const availableBanks = useMemo(() => SUPPORTED_BANK_OPTIONS.filter(({ available }) => available), [])

  const syncPrimaryBank = (selectedBanks: BankName[]) => {
    const primaryBank = selectedBanks[0] ?? ''
    setDetails((prev) => ({
      ...prev,
      bankName: primaryBank,
      selectedBanks,
    }))
  }

  const addSelectedBank = () => {
    if (!bankToAdd) {
      setError('Please choose a bank to add.')
      return
    }

    if (details.selectedBanks.includes(bankToAdd)) {
      setError(`${bankToAdd} is already selected.`)
      return
    }

    setError(null)
    syncPrimaryBank([...details.selectedBanks, bankToAdd])
    setBankToAdd('')
  }

  const removeBank = (bank: BankName) => {
    const nextBanks = details.selectedBanks.filter((item) => item !== bank)
    setError(null)
    syncPrimaryBank(nextBanks)
  }

  const handleSubmit = () => {
    const validationError = validateUserDetails(details)
    if (validationError) {
      setError(validationError)
      return
    }

    setError(null)
    onSubmit(details)
  }

  const isComplete =
    details.fullName.trim() !== '' &&
    details.selectedBanks.length > 0

  return (
    <div className="animate-fade-in">
      <div className="space-y-6">
        <div>
          <label
            htmlFor="fullName"
            className="block text-sm font-medium text-black mb-1.5"
          >
            Full Name
          </label>
          <input
            id="fullName"
            type="text"
            placeholder="Enter your full name"
            value={details.fullName}
            onChange={(e) => setDetails({ ...details, fullName: e.target.value })}
            className="w-full px-4 py-2.5 border border-border rounded-md text-sm text-black placeholder:text-neutral-400 bg-white focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-1 transition-shadow"
          />
        </div>

        <p className="text-sm text-neutral-500">
          You’ll choose the bank statement type for each bank on the next step.
        </p>

        <div>
          <div className="flex items-center justify-between gap-3 mb-1.5">
            <label
              htmlFor="bankSelect"
              className="block text-sm font-medium text-black"
            >
              Bank Name
            </label>
            <span className="text-[11px] text-neutral-400">
              Add as many banks as needed
            </span>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <select
              id="bankSelect"
              value={bankToAdd}
              onChange={(e) => setBankToAdd(e.target.value as BankName | '')}
              className="w-full flex-1 px-4 py-2.5 border border-border rounded-md text-sm bg-white text-black appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-1 transition-shadow"
            >
              <option value="">Select a bank</option>
              {availableBanks.map(({ name }) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={addSelectedBank}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-black bg-black px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-neutral-800"
            >
              <Plus className="h-4 w-4" />
              Add Another Bank
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {details.selectedBanks.length > 0 ? (
              details.selectedBanks.map((bank) => (
                <span
                  key={bank}
                  className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-sm text-black"
                >
                  {bank}
                  <button
                    type="button"
                    onClick={() => removeBank(bank)}
                    className="rounded-full p-0.5 text-neutral-500 transition hover:bg-white hover:text-black"
                    aria-label={`Remove ${bank}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))
            ) : (
              <p className="text-sm text-neutral-400">
                No banks selected yet.
              </p>
            )}
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <button
          onClick={handleSubmit}
          disabled={!isComplete}
          className="w-full py-2.5 bg-black text-white text-sm font-medium rounded-md hover:bg-neutral-800 disabled:bg-neutral-300 disabled:cursor-not-allowed transition-colors"
        >
          Continue
        </button>
      </div>
    </div>
  )
}
