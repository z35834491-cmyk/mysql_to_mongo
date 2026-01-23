import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

class Request {
  private instance: AxiosInstance
  
  constructor() {
    this.instance = axios.create({
      baseURL: '/api',
      timeout: 30000, // Increase global timeout to 30s
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    this.setupInterceptors()
  }
  
  private setupInterceptors() {
    // Request interceptor
    this.instance.interceptors.request.use(
      (config) => {
        return config
      },
      (error) => Promise.reject(error)
    )
    
    // Response interceptor
    this.instance.interceptors.response.use(
      (response: AxiosResponse) => {
        return response.data
      },
      (error) => {
        // Handle Session Timeout (401 or 403 when session expired)
        if (error.response?.status === 401 || (error.response?.status === 403 && error.response?.data?.detail?.includes('authentication'))) {
          ElMessage.error('Session expired. Please login again.')
          window.location.href = '/accounts/login/'
          return Promise.reject(error)
        }

        // Silently ignore 401/404 for /api/me during initial load
        const isMeError = error.config?.url?.includes('/me')
        if (isMeError && (error.response?.status === 401 || error.response?.status === 404)) {
          return Promise.reject(error)
        }

        const msg = error.response?.data?.detail || error.response?.data?.error || error.message || 'Request failed'
        ElMessage.error(msg)
        return Promise.reject(error)
      }
    )
  }
  
  public get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.get(url, config)
  }
  
  public post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.post(url, data, config)
  }
  
  public put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.put(url, data, config)
  }
  
  public delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.delete(url, config)
  }
}

export default new Request()
