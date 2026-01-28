import { createApp } from 'vue'
import { createPinia } from 'pinia'
// import ElementPlus from 'element-plus' // Removed for auto-import optimization
// import 'element-plus/dist/index.css' // Removed for auto-import optimization
import App from './App.vue'
import router from './router'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

// Register Icons globally (keeping this for convenience as icons are often dynamic)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
// app.use(ElementPlus) // Removed for auto-import optimization

app.mount('#app')
