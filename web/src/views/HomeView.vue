<script setup lang="ts">
document.title = "Home - Archive your research drive"
</script>

<template>
  <main>
    <h1 class="page-title">Archive your research drive</h1>
    <section class="content">
    <section>
    <p>Use this service if you have a research storage drive you no longer use.</p>
    <p>You can use this service to:</p>
    <ul>
      <li>Confirm you want to archive the research drive. </li>
      <li>Check and update research storage drive details.</li>
      <li>Declare data classification and retention period for the stored files.</li>
      <li>Add additional metadata to annotate your files.</li>
    </ul>
    <section class="forward-btn">
      <RouterLink class="btn btn-primary" to="/summary">Start</RouterLink>
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
    <!-- <section class="before-you-start">
      <h2>Before you start</h2>
      <p>This service will ask you to confirm details such as .  Ensure you and your collaborators no longer actively use this drive. </p>
    </section> -->
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