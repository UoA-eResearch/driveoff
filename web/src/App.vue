<script setup lang="ts">
import { RouterView } from 'vue-router'
import { formState, requestInfo } from './store';
import { client } from './client';
import { loadRequestInfo } from './client/requestInfo';
import { onErrorCaptured } from 'vue';

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

client.interceptors.request.use((request, _) => {
  request.headers.set('x-api-key', import.meta.env.VITE_API_KEY);
  return request;
});

// Load initial request information - project and drive.
loadRequestInfo();
</script>

<template>
  <header>
    <img src="/logo.png" width="200" alt="Logo for Waipapa Taumata Rau University of Auckland" />
  </header>

  <RouterView />
</template>

<style scoped>
  header {
    padding: 1rem 0;
  }
</style>
