import { BankName } from '@/types'

export interface BankOption {
  name: BankName
  available: boolean
}

export const SUPPORTED_BANK_OPTIONS: BankOption[] = [
  { name: 'HDFC Bank', available: true },
  { name: 'ICICI Bank', available: true },
  { name: 'Axis Bank', available: true },
  { name: 'Kotak Bank', available: true },
  { name: 'SBI', available: true },
  { name: 'Canara Bank', available: true },
  { name: 'IDFC First Bank', available: true },
  { name: 'Karnataka Bank', available: true },
  { name: 'Paytm Bank', available: true },
  { name: 'Union Bank of India', available: true },
  { name: 'Bank of Baroda', available: true },
  { name: 'Bank of India', available: true },
  { name: 'Indian Bank', available: true },
  { name: 'Unknown', available: true },
]

export const SUPPORTED_BANK_NAMES = new Set<BankName>(
  SUPPORTED_BANK_OPTIONS.map(({ name }) => name)
)

export const isSupportedBankName = (value: string): value is BankName =>
  SUPPORTED_BANK_NAMES.has(value as BankName)
