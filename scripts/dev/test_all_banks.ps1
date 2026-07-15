# Test all banks systematically
# Usage: .\scripts\test_all_banks.ps1

$ErrorActionPreference = "Continue"

# Configuration
$BackendUrl = "http://localhost:8000"
$TestResults = @()

# Banks to test with sample PDFs
$TestCases = @(
    @{ Bank = "HDFC"; File = "banks\hdfc\hdfcsiva_1685441504280.pdf"; BankName = "HDFC Bank" },
    @{ Bank = "Karnataka"; File = "banks\karnataka bank\9522XXXXXXXX3801_3213191630_1690884667992.pdf"; BankName = "Karnataka Bank" },
    @{ Bank = "SBI"; File = "banks\sbi\9515_11072_1720671808775.pdf"; BankName = "SBI" },
    @{ Bank = "Axis"; File = "banks\axis\Axis_bankstatement.pdf"; BankName = "Axis Bank" },
    @{ Bank = "ICICI"; File = "banks\icici\ICICI-3M_1685081454384.pdf"; BankName = "ICICI Bank" },
    @{ Bank = "Canara"; File = "banks\canara\CanaraStm_1708930616809.pdf"; BankName = "Canara Bank" },
    @{ Bank = "Kotak"; File = "banks\kotak\61XXXXX357_1748243671168.pdf"; BankName = "Kotak Mahindra Bank" },
    @{ Bank = "Union"; File = "banks\union\Union_Bank_Statement.pdf"; BankName = "Union Bank of India" },
    @{ Bank = "IDFC"; File = "banks\idfc\IDFCFIRSTBankstatement_10072076528(1)_1685342952820.pdf"; BankName = "IDFC First Bank" },
    @{ Bank = "BankOfBaroda"; File = "banks\bank of baroda\Statement_1733922833120.pdf"; BankName = "Bank of Baroda" },
    @{ Bank = "Paytm"; File = "banks\paytm\Account_Statement_010423_110723_1689140433613.pdf"; BankName = "Paytm Payments Bank" }
)

Write-Host "=== Testing All Banks ===" -ForegroundColor Cyan
Write-Host ""

# Check backend health first
Write-Host "Checking backend health..." -ForegroundColor Yellow
try {
    $Health = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 10
    Write-Host "✅ Backend is healthy" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend is not responding: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test each bank
foreach ($Test in $TestCases) {
    $Bank = $Test.Bank
    $FilePath = $Test.File
    $BankName = $Test.BankName
    
    Write-Host "Testing $BankName..." -ForegroundColor Yellow
    
    $Result = @{
        Bank = $Bank
        BankName = $BankName
        File = $FilePath
        Upload = "FAILED"
        StatusCode = $null
        Error = $null
    }
    
    # Check if file exists
    if (-not (Test-Path $FilePath)) {
        Write-Host "  ⚠️  File not found: $FilePath" -ForegroundColor Yellow
        $Result.Error = "File not found"
        $TestResults += $Result
        continue
    }
    
    # Test upload
    try {
        $Form = @{
            file = Get-Item -Path $FilePath
            bank_name = $BankName
            mode = "free"
        }
        
        $Headers = @{
            "Authorization" = "Bearer test-token"
            "X-API-Key" = "test-api-key"
        }
        
        $Response = Invoke-RestMethod -Uri "$BackendUrl/api/upload/bank-statement-async" `
            -Method POST -Form $Form -Headers $Headers -TimeoutSec 30
        
        $Result.Upload = "SUCCESS"
        $Result.StatusCode = 200
        $Result.JobId = $Response.job_id
        Write-Host "  ✅ Upload successful (Job: $($Response.job_id))" -ForegroundColor Green
        
        # Poll for job status (max 60 seconds)
        $JobId = $Response.job_id
        $MaxAttempts = 30
        $Attempt = 0
        $JobComplete = $false
        
        while ($Attempt -lt $MaxAttempts -and -not $JobComplete) {
            Start-Sleep -Seconds 2
            $Attempt++
            
            try {
                $JobStatus = Invoke-RestMethod -Uri "$BackendUrl/api/jobs/$JobId" `
                    -Headers $Headers -TimeoutSec 10
                
                if ($JobStatus.status -eq "completed") {
                    $JobComplete = $true
                    $Result.Processing = "SUCCESS"
                    $Result.Transactions = $JobStatus.transactions_processed
                    Write-Host "  ✅ Processing complete ($($JobStatus.transactions_processed) transactions)" -ForegroundColor Green
                } elseif ($JobStatus.status -eq "failed") {
                    $JobComplete = $true
                    $Result.Processing = "FAILED"
                    $Result.Error = $JobStatus.error_message
                    Write-Host "  ❌ Processing failed: $($JobStatus.error_message)" -ForegroundColor Red
                }
            } catch {
                # Continue polling
            }
        }
        
        if (-not $JobComplete) {
            $Result.Processing = "TIMEOUT"
            Write-Host "  ⏱️  Processing timed out" -ForegroundColor Yellow
        }
        
    } catch {
        $Result.StatusCode = $_.Exception.Response.StatusCode.value__
        $Result.Error = $_.Exception.Message
        Write-Host "  ❌ Upload failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    $TestResults += $Result
    Write-Host ""
}

# Summary
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host ""

$SuccessCount = ($TestResults | Where-Object { $_.Upload -eq "SUCCESS" -and $_.Processing -eq "SUCCESS" }).Count
$FailedCount = $TestResults.Count - $SuccessCount

Write-Host "Successful: $SuccessCount / $($TestResults.Count)" -ForegroundColor Green
Write-Host "Failed: $FailedCount / $($TestResults.Count)" -ForegroundColor Red
Write-Host ""

# Show failed banks
$FailedBanks = $TestResults | Where-Object { $_.Upload -ne "SUCCESS" -or $_.Processing -ne "SUCCESS" }
if ($FailedBanks) {
    Write-Host "Failed Banks:" -ForegroundColor Red
    foreach ($Bank in $FailedBanks) {
        Write-Host "  - $($Bank.BankName): $($Bank.Error)" -ForegroundColor Red
    }
}

# Export results
$TestResults | Export-Csv -Path "test_results.csv" -NoTypeInformation
Write-Host ""
Write-Host "Results saved to test_results.csv" -ForegroundColor Cyan
