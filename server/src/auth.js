export function getBearerToken(req) {
  const header = req.headers.authorization
  if (!header) return null
  const [scheme, token] = header.split(" ")
  if (scheme?.toLowerCase() !== "bearer") return null
  return token || null
}

export function makeAuthMiddleware(world) {
  return function authMiddleware(req, res, next) {
    const token = getBearerToken(req)
    if (!token) {
      res.status(401).json({ error: "missing_bearer_token" })
      return
    }

    const agent = world.getAgentByToken(token)
    if (!agent) {
      res.status(401).json({ error: "invalid_token" })
      return
    }

    if (!agent.alive) {
      res.status(403).json({ error: "agent_eliminated" })
      return
    }

    req.agent = agent
    next()
  }
}

