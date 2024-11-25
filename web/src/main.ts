import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { formState } from './store'
import { getProject } from './fixtures'

const app = createApp(App)

// Initialise the form project state with initial data from server.
formState.project = getProject();

app.use(router)

app.mount('#app')
