import { request } from './client'

interface LoginResponse {
  access_token: string
  token_type: string
  user: { id: string; username: string }
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const data = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  localStorage.setItem('token', data.access_token)
  return data
}

export async function register(username: string, password: string) {
  const data = await request<{ id: string; username: string }>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  return data
}
