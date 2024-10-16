<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
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
