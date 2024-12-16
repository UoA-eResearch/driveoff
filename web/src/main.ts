import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(router)

// Global error handler
app.config.errorHandler = (err, instance, info) => {

    // Handle the error globally
    console.error("Global error:", err);
    console.log("Vue instance:", instance);
    console.log("Error info:", info);

    router.replace("/service-error");
};

app.mount('#app')
