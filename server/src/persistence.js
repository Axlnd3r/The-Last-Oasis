import fs from "node:fs/promises"
import path from "node:path"

export async function loadJsonState(stateFilePath, makeDefaultState) {
  try {
    const raw = await fs.readFile(stateFilePath, "utf8")
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") throw new Error("Invalid state file")
    return parsed
  } catch (err) {
    if (err?.code !== "ENOENT") {
      throw err
    }
    const initial = makeDefaultState()
    await saveJsonState(stateFilePath, initial)
    return initial
  }
}

export async function saveJsonState(stateFilePath, state) {
  const dir = path.dirname(stateFilePath)
  await fs.mkdir(dir, { recursive: true })
  const tmpFile = `${stateFilePath}.tmp`
  const payload = JSON.stringify(state, null, 2)
  await fs.writeFile(tmpFile, payload, "utf8")
  await fs.rename(tmpFile, stateFilePath)
}

