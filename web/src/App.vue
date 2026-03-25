<script setup lang="ts">
import { RouterView } from 'vue-router'
import { formState, requestInfo } from './store';
import { client } from './client/client.gen';
import { loadRequestInfo } from './service/requestInfo';
import router from './router';

window.addEventListener('beforeunload', (event) => {
  // If the user has started the form but hasn't finished it, give a warning before
  // they close the tab.
  if ((formState.hasStartedForm && !formState.hasFinishedForm)) {
    event.preventDefault();
    event.returnValue = true;
  }
});

// Set up API client.
client.setConfig({
  baseUrl: import.meta.env.VITE_API_BASE_URL
});

client.interceptors.request.use((request) => {
  request.headers.set('x-api-key', import.meta.env.VITE_API_KEY);
  return request;
});

// Load initial request information - project and drive.
loadRequestInfo().then((hasLoadedRequestInfo: boolean) => {
  if (!hasLoadedRequestInfo) {
    // If loading the request info wasn't successful, redirect to error page.
    router.replace("/service-error");
  }
});
</script>

<template>
  <header>
    <img src="/logo.png" width="200" alt="Logo for Waipapa Taumata Rau University of Auckland" />
  </header>

  <div v-if="requestInfo.isLoading" class="loading-indicator">
    <div>Loading drive information</div>
    <div class="spinner"></div>
  </div>
  <RouterView v-else />
</template>

<style scoped>
  header {
    padding: 1rem 0;
  }

  .loading-indicator {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 200px;
    font-size: 1.2rem;
  }
  .spinner {
    border: 8px solid var(--brand-light); /* Light grey background ring */
    border-top: 8px solid var(--brand-primary); /* Blue spinning part */
    border-radius: 50%;
    width: 50px;
    height: 50px;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>
