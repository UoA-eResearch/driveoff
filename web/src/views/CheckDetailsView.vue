<script setup lang="ts">
import { membersToString, getProjectMembers, getProjectOwners } from '@/models/helpers';
import { formState, requestInfo } from '@/store';
import { ref } from 'vue';
import { useRouter } from 'vue-router';


const DOCUMENT_TITLE = "Confirm project information - Archive your research drive";
document.title = DOCUMENT_TITLE;

const error =ref("");
const router = useRouter();
const owners = membersToString(getProjectOwners(requestInfo.project.members ?? []));
const members = membersToString(getProjectMembers(requestInfo.project.members ?? []));

function tryContinue() {
    if (formState.areProjectDetailsCorrect === null){
        document.title = "Error: " + DOCUMENT_TITLE;
        error.value = "Select Yes if the project information is still correct.";
    } else if (formState.areProjectDetailsCorrect) {
            router.push("/data-classification");
    } else {
        // Project editing is not currently supported.
        // If details are wrong, user should contact eResearch.
        router.push("/unable-to-archive");
    }
}
</script>

<template>
  <main>
    <h1 class="app-title">
      Archive your research drive
    </h1>
    <div class="title-section">
      <h2 class="page-title">
        Check project information
      </h2>
      <p>Project information describes the files in the research drive and the people who have access and rights to the files. </p> 
      <!-- <p>It is entered when the research drive was requested, but may become incorrect over time. For example, the project may have changed research focus, or people may have joined or left the project.</p> -->
      <p>Correct project information is important for archiving. If required, the information is used to find the right archived files and determine whether to grant or deny access requests.</p> 
    </div> 
    <section class="project-details-card box">
      <h3 class="h2">
        Project information for {{ requestInfo.drive.name }}
      </h3>
      <dl class="other-details">
        <dt>Title</dt>
        <dl>{{ requestInfo.project.title }}</dl>
        <dt>Description</dt>
        <dl>{{ requestInfo.project.description }}</dl>
        <dt>Project owner</dt>
        <dl>{{ owners }}</dl>
        <dt>Project members</dt>
        <dl>{{ members }}</dl>
        <dt>Department</dt>
        <dl>{{ requestInfo.project.division }}</dl>
      </dl>
    </section>
    <form
      novalidate
      :class="{ error : error }"
      @submit.prevent="tryContinue()"
    >
      <fieldset>
        <legend class="h2">
          Is the project information still correct?
        </legend>
        <p
          v-if="error"
          class="error-msg"
        >
          {{ error }}
        </p>
        <div class="option-list">
          <input
            id="yes-project"
            v-model="formState.areProjectDetailsCorrect"
            name="confirm-project"
            type="radio"
            :value="true"
          >
          <label for="yes-project">Yes, it is.</label>
          <input
            id="no-project"
            v-model="formState.areProjectDetailsCorrect"
            name="confirm-project"
            type="radio"
            :value="false"
          >
          <label for="no-project">No, it needs to be updated.</label>
        </div>
      </fieldset>
    </form>
    <section class="forward-btn">
      <a
        class="btn btn-primary"
        @click.prevent="tryContinue()"
      >Continue</a>
    </section>
  </main>
</template>

<style scoped>
.other-details {
    margin-top: 1rem;
}
td {
    padding: 0.5rem;
    border-bottom: 1px solid gray;
    /* background-color: lightgray; */
    
}
td:first-child {
    font-family: "Inter", sans-serif;
    font-weight: 700;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

.project-details-card {
    padding-left: 1rem;
    padding: 1rem;
    margin: 2rem 0;
    width: fit-content;
}

.project-name {
    font-family: "Inter", sans-serif;
    font-weight: 700;
}

dt {
    font-family: "Inter", sans-serif;
    font-weight: 700;
}

dt:not(:first-child) {
    margin-top: 1rem;
}
/* table {
    width: 100%; */
/* } */
</style>