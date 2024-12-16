<script setup lang="ts">
import { formState } from '@/store';
import { useRouter } from 'vue-router';

const router = useRouter();
document.title = "Home - Archive your research drive";

function nextStep() {
  formState.hasStartedForm = true;
  router.push("/summary")
}

</script>

<template>
  <main>
    <h1 class="page-title">Archive your research drive</h1>
    <section class="content">
    <section>
    <p>Use this service if you have a research storage drive you no longer use.</p>
    <p>You can use this service to:</p>
    <ul>
      <li>Check and update research storage drive details.</li>
      <li>Declare data classification and retention period for the stored files.</li>
      <li>Confirm you want to archive the research drive. </li>
    </ul>
    <section class="forward-btn">
      <a @click="nextStep()" class="btn btn-primary">Start</a>
    </section>
    <section class="more-info">
      <h2 class="h2">What does archiving do?</h2>
      <p>The files in your research drive will be archived and moved to tape storage, a slower storage medium suitable for backup. This frees up space for other research projects. You can specify how long the files need to be retained for. You can get a copy of the archived research drive files. See <a href="https://research-hub.auckland.ac.nz" target="_blank">ResearchHub</a> for more information.</p>
      <h2 class="h2">If you need help</h2>
      <p><a href="https://eresearch.auckland.ac.nz">Contact Centre for eResearch</a> for help with any questions while using this service.</p>
    </section>
  </section>
  <section class="related-content">
    <h2>Related links</h2>
    <ul>
      <li><a href="https://research-hub.auckland.ac.nz/managing-research-data/research-data-storage/research-drive">Information about Research Drive</a></li>
    </ul>
  </section>
  </section>
  </main>
</template>

<style scoped>


.related-content h2 {
  font-size: 1.4rem;
  margin-bottom: 1.5rem;
  font-family: NationalBook, sans-serif;
}

/* 
.before-you-start {
  margin-top: 2rem;
} */

.related-content {
  width: 500px;
  background-color: #0080a7;
  padding: 1.4rem 1.66rem;
  height: 100%;
}

.related-content * {
  color: white;
  text-decoration: none;
}

/* @media (min-width: 1024px) {
  .related-content {
    width: 700px;
  }
} */

.content {
  display: flex;
  gap: 3rem;
}
</style>