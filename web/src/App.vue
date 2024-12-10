<script setup lang="ts">
import { RouterView } from 'vue-router'
import { formState } from './store';
import { client } from './client';

window.addEventListener('beforeunload', (event) => {
  // If the user has started the form but hasn't finished it, give a warning before
  // they close the tab.
  if ((formState.hasStartedForm && !formState.hasFinishedForm)) {
    event.preventDefault();
    event.returnValue = true;
  }
});

client.setConfig({
  baseUrl: "http://localhost:8000"
});

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
