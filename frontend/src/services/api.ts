interface HealthResponse {
  status: string
  service: string
}

export const api = {
  async checkHealth(): Promise<HealthResponse> {
    const response = await fetch('/api/health')
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`)
    }
    return response.json()
  },
}
