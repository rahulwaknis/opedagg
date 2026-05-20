<#
create_and_push_repo.ps1

Usage:
  # interactive (will prompt for repo name if missing)
  .\create_and_push_repo.ps1

  # non-interactive
  .\create_and_push_repo.ps1 -RepoName "my-repo" -Visibility public

Notes:
- This script prefers the GitHub CLI (`gh`). If `gh` is not installed it will try to use the GitHub API and requires `GITHUB_TOKEN` environment variable with `repo` scope.
- Replace `https://github.com/<your-username>/<repo>.git` style URLs if you prefer SSH.
#>

param(
    [string]$RepoName,
    [ValidateSet("public","private")] [string]$Visibility = "public",
    [switch]$SkipPush
)

function Fail($msg) { Write-Error $msg; exit 1 }

# ensure git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "`git` not found. Please install Git and retry."
}

# init repo if needed
if (-not (Test-Path .git)) {
    git init
}

# stage all files
git add -A

# commit if changes
$status = git status --porcelain
if ($status) {
    git commit -m "Initial commit — render manifest and deploy files"
} else {
    Write-Host "No changes to commit."
}

# ensure main branch
try {
    git branch -M main 2>$null
} catch {
    # ignore
}

if (-not $RepoName) {
    $RepoName = Read-Host "Enter GitHub repo name (owner/repo or repo)"
}

if (-not $RepoName) { Fail "No repository name provided." }

# prefer gh if available
$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    Write-Host "Using GitHub CLI (gh) to create and push the repo..."
    $pubFlag = if ($Visibility -eq 'public') { '--public' } else { '--private' }

    # create via gh; -y to skip prompts
    gh repo create $RepoName $pubFlag --source=. --remote=origin --push -y
    if ($LASTEXITCODE -ne 0) {
        Fail "gh repo create failed. Check gh authentication and repo name."
    }
    Write-Host "Repository created and pushed via gh."
    exit 0
}

# fallback: use GitHub API with GITHUB_TOKEN
Write-Host "gh CLI not found. Falling back to GitHub API; requires GITHUB_TOKEN environment variable."
$token = $env:GITHUB_TOKEN
if (-not $token) { Fail "GITHUB_TOKEN not found in environment. Install gh or set GITHUB_TOKEN with repo scope." }

# parse repo name
if ($RepoName -match '/') {
    $parts = $RepoName.Split('/')
    $owner = $parts[0]
    $name = $parts[1]
} else {
    $owner = $null
    $name = $RepoName
}

$body = @{ name = $name; private = ($Visibility -eq 'private') } | ConvertTo-Json

if ($owner) {
    $apiUrl = "https://api.github.com/orgs/$owner/repos"
} else {
    $apiUrl = "https://api.github.com/user/repos"
}

try {
    $resp = Invoke-RestMethod -Method Post -Uri $apiUrl -Headers @{ Authorization = "token $token"; "User-Agent" = "op-ed-network-deployer" } -Body $body -ContentType "application/json"
} catch {
    Fail "Failed to create repo via GitHub API: $($_.Exception.Message)"
}

if (-not $resp) { Fail "Empty response from GitHub API." }

$cloneUrl = $resp.clone_url
$repoHtml = $resp.html_url

# set remote (override if exists)
$existing = git remote
if ($existing -match 'origin') {
    git remote remove origin
}

git remote add origin $cloneUrl

if (-not $SkipPush) {
    git push -u origin main
}

Write-Host "Repository created: $repoHtml"
Write-Host "Pushed to origin/main."
exit 0
