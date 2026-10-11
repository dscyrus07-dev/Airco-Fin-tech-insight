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

/**
 * Fallback for GET /api/statements/banks when the API is unreachable.
 * ids mirror PIPELINE_BANK_NAME in backend/app/services/analysis_service.py.
 * The API remains the primary source; this only keeps the UI usable offline.
 */
export const FALLBACK_BANK_LIST: { id: string; name: BankName }[] = [
  { id: 'hdfc', name: 'HDFC Bank' },
  { id: 'icici', name: 'ICICI Bank' },
  { id: 'axis', name: 'Axis Bank' },
  { id: 'kotak', name: 'Kotak Bank' },
  { id: 'sbi', name: 'SBI' },
  { id: 'canara', name: 'Canara Bank' },
  { id: 'idfc', name: 'IDFC First Bank' },
  { id: 'karnataka', name: 'Karnataka Bank' },
  { id: 'paytm', name: 'Paytm Bank' },
  { id: 'union', name: 'Union Bank of India' },
  { id: 'bank_of_baroda', name: 'Bank of Baroda' },
  { id: 'bank_of_india', name: 'Bank of India' },
  { id: 'indian_bank', name: 'Indian Bank' },
]
