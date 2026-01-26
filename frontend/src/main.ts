import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus is now auto-imported
import 'element-plus/dist/index.css' 
import App from './App.vue'
import router from './router'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
// app.use(ElementPlus) // Removed full import

app.mount('#app')
