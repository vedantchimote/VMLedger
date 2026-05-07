# Test registration with a simple password

$password = "TestPass123!"

$body = @{
    username = "testuser"
    email = "test@example.com"
    password = $password
} | ConvertTo-Json

Write-Host "Testing registration with password: $password" -ForegroundColor Yellow
Write-Host "Password length: $($password.Length) characters" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/register" `
        -Method Post `
        -Body $body `
        -ContentType "application/json" `
        -ErrorAction Stop
    
    Write-Host "✅ Registration successful!" -ForegroundColor Green
    Write-Host "User ID: $($response.data.user_id)" -ForegroundColor Cyan
    Write-Host "Username: $($response.data.username)" -ForegroundColor Cyan
    Write-Host "Email: $($response.data.email)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Registration failed!" -ForegroundColor Red
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Yellow
    
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    $responseBody = $reader.ReadToEnd()
    $reader.Close()
    
    Write-Host "Error Response:" -ForegroundColor Yellow
    Write-Host $responseBody -ForegroundColor Red
}
