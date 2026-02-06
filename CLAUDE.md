# Project Instructions

## exe.dev Platform Knowledge

This project runs on the exe.dev platform - on-demand Linux VMs accessible via the internet.

### Platform Features
- HTTP proxies for private/public internet publishing
- Custom domain support (CNAME integration)
- SSH-based access with configurable keys
- Cross-VM networking via SSH or Tailscale
- Docker container support
- VSCode remote connection capability
- GitHub token support with fine-grained options
- Email send/receive capabilities

### Architecture: "GUTS Stack"
- Go, Unix, TypeScript, SQLite
- "Serverful" approach (persistent disks, not serverless)
- Isolated VM sandboxing for security

### HTTPS Proxy Configuration

**Port Selection:**
- Auto-selects from exposed Dockerfile ports (prioritizes port 80, then smallest TCP >= 1024)
- Manual override: `ssh exe.dev share port <vmname> <port>`

**Access Control:**
- Private (default): Only users with VM access; redirects to login
- Public: `ssh exe.dev share set-public <vmname>`
- Revert to private: `ssh exe.dev share set-private <vmname>`

**Port Forwarding:**
- Transparently forwards ports 3000-9999
- Only one port can be marked public
- Other ports accessible to authorized VM users only

**Request Headers Added by Proxy:**
- `X-Forwarded-Proto` - original TLS status
- `X-Forwarded-Host` - client-requested host
- `X-Forwarded-For` - client IP chain

### Limitations & Best Practices

1. **Use documented features only** - Undocumented local endpoints are internal infrastructure and unstable
2. **Port range** - Proxy only forwards ports 3000-9999
3. **Single public port** - Only one port can be made public at a time
4. **Private by default** - VMs require authentication unless explicitly made public

### Documentation References
- Main docs: https://exe.dev/docs.md
- Proxy docs: https://exe.dev/docs/proxy.md
