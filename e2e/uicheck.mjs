import { readFileSync } from 'fs'
const ENV = {}
for (const line of readFileSync('X:/Airco Projects/Airco Insights fintech/wt-demo/local.env', 'utf-8').split('\n')) {
  const m = line.replace(/\r$/, '').match(/^([A-Z_0-9]+)=(.*)$/)
  if (m) ENV[m[1]] = m[2].trim().replace(/^"|"$/g, '')
}
const body = new URLSearchParams({ grant_type: 'password', client_id: 'frontend-app',
  client_secret: ENV.KEYCLOAK_CLIENT_SECRET || '', username: ENV.TEST_USER_EMAIL || 'test@airco.com',
  password: ENV.TEST_USER_PASSWORD || 'Test123!', scope: 'openid' })
const tk = await (await fetch('http://localhost:8080/realms/airco-insights/protocol/openid-connect/token',
  { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })).json()
const H = { Authorization: `Bearer ${tk.access_token}` }
const hist = await (await fetch('http://localhost:8101/api/profile/history', { headers: H })).json()
const withAcct = (hist.uploads || []).find(u => u.account_type === 'salaried')
console.log('salaried job:', withAcct.job_id.slice(0,8))
const j = await (await fetch(`http://localhost:8101/api/jobs/${withAcct.job_id}`, { headers: H })).json()
console.log('input_data keys:', Object.keys(j.input_data || {}))
console.log('user_info:', JSON.stringify((j.input_data || {}).user_info))
