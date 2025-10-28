# Security Improvements

This document outlines the security improvements made to prepare the AIS Ship Simulator for public GitHub release.

## Changes Made

### 1. Removed Hardcoded Credentials

**Setup Scripts:**
- `setup_mongodb.js`: Now requires `SHIPSIM_APP_PASSWORD` environment variable instead of hardcoded password
- `setup_mongodb_admin.js`: Removed hardcoded admin user references

**Python Application:**
- No default passwords in code
- All credentials must be explicitly provided

### 2. Implemented Secure Password Handling

The simulator now supports three methods for password input (in order of precedence):

#### Method 1: Command Line (Least Secure)
```bash
python ship_simulator.py --mongodb-user shipsim_app --mongodb-password "your_password"
```
**Warning:** Not recommended as passwords may be visible in process lists and shell history.

#### Method 2: Environment Variable (Recommended for Scripts)
```bash
export MONGODB_PASSWORD="your_password"
python ship_simulator.py --mongodb-user shipsim_app
```
**Use when:** Running automated scripts or in containerized environments.

#### Method 3: Interactive Prompt (Most Secure)
```bash
python ship_simulator.py --mongodb-user shipsim_app
# Password will be prompted securely
```
**Use when:** Running manually/interactively. Password input is hidden.

### 3. Updated Documentation

All documentation files have been updated to remove example credentials:
- `README.md`
- `QUICK_START.md`
- `MONGODB_GUIDE.md`

Examples now show:
- `<admin-user>` instead of specific usernames
- `--password` flag without values (prompts interactively)
- Environment variable usage instead of hardcoded passwords

### 4. Added .gitignore

Created comprehensive `.gitignore` file to prevent committing:
- Credentials files (`.env`, `*.key`, `credentials.json`, etc.)
- Virtual environment (`venv/`)
- Python cache files
- Database files
- IDE files

## Setup Instructions for New Users

### 1. Create MongoDB Users

Set a secure password for the application user:

```bash
export SHIPSIM_APP_PASSWORD="choose_a_secure_password_here"
mongosh --username <your-admin-user> --password --authenticationDatabase admin < setup_mongodb_admin.js
mongosh --username <your-admin-user> --password --authenticationDatabase admin < setup_mongodb.js
```

### 2. Run the Simulator

**Interactive mode (recommended):**
```bash
python ship_simulator.py --mongodb-user shipsim_app
# Enter password when prompted
```

**Automated/scripted mode:**
```bash
export MONGODB_PASSWORD="your_password"
python ship_simulator.py --mongodb-user shipsim_app
```

## Security Best Practices

### For Development

1. **Use interactive prompts** when running manually
2. **Store passwords in environment variables**, not in scripts
3. **Never commit** `.env` files or any credentials to git
4. **Use different passwords** for development vs production

### For Production

1. **Use strong, unique passwords** (minimum 16 characters, mixed case, numbers, symbols)
2. **Enable MongoDB authentication** and SSL/TLS
3. **Restrict network access** to MongoDB using firewall rules
4. **Use secrets management** systems (HashiCorp Vault, AWS Secrets Manager, etc.)
5. **Rotate credentials regularly**
6. **Enable MongoDB audit logging**
7. **Use read-only users** where write access isn't needed

### For CI/CD

1. **Store credentials in CI secrets** (GitHub Secrets, GitLab CI/CD variables, etc.)
2. **Use temporary credentials** where possible
3. **Limit credential scope** to minimum required permissions
4. **Audit secret access** regularly

## Password Priority

When `--mongodb-user` is provided, passwords are checked in this order:

1. `--mongodb-password` command line argument (if provided)
2. `MONGODB_PASSWORD` environment variable (if set)
3. Interactive prompt (if neither above is available)

## Environment Variables

The simulator recognizes these environment variables:

- `MONGODB_PASSWORD`: Password for MongoDB authentication
- `SHIPSIM_APP_PASSWORD`: Used by `setup_mongodb.js` to create the app user

## Migration from Previous Versions

If you were using hardcoded credentials (from earlier versions):

1. **Update setup scripts:**
   ```bash
   export SHIPSIM_APP_PASSWORD="your_new_secure_password"
   mongosh --username <admin> --password --authenticationDatabase admin < setup_mongodb.js
   ```

2. **Update simulator invocations:**
   ```bash
   # Old (insecure):
   python ship_simulator.py --mongodb-user shipsim_app --mongodb-password shipsim_app

   # New (secure):
   export MONGODB_PASSWORD="your_new_secure_password"
   python ship_simulator.py --mongodb-user shipsim_app
   ```

## Files Safe to Commit

These files are safe to commit to public repositories:

- ✅ `ship_simulator.py` - No credentials
- ✅ `setup_mongodb.js` - No credentials (requires env var)
- ✅ `setup_mongodb_admin.js` - No credentials
- ✅ All `.md` documentation files
- ✅ `.gitignore`

## Files to NEVER Commit

- ❌ `.env` files
- ❌ Any file with actual passwords/credentials
- ❌ `venv/` directory
- ❌ Configuration files with connection strings containing passwords
- ❌ Shell scripts with embedded passwords

## Checking for Leaked Credentials

Before committing, check for accidental credential exposure:

```bash
# Search for potential passwords in tracked files
git grep -i password
git grep -i secret
git grep -i credential

# Check git history for leaked credentials
git log -S "password" --all
```

If credentials were accidentally committed:

```bash
# Use git-filter-repo or BFG Repo-Cleaner to remove from history
# See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
```

## Questions?

For security concerns or questions:
- Review this document
- Check the documentation in `MONGODB_GUIDE.md`
- See `QUICK_START.md` for usage examples
- File an issue on GitHub (without including any credentials!)

## Security Checklist for GitHub Release

- [x] All hardcoded credentials removed
- [x] Password prompting implemented
- [x] Documentation updated
- [x] .gitignore created
- [x] Setup scripts use environment variables
- [x] Security documentation created
- [ ] Review all files one more time before pushing
- [ ] Ensure no `.env` or credential files in working directory
- [ ] Test clean clone and setup process
