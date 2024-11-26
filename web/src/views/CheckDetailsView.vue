<script setup lang="ts">
import { getDrive, getProject } from '@/fixtures';
import { membersToString, getProjectMembers, getProjectOwners } from '@/project';
import { formState } from '@/store';
import { ref } from 'vue';
import { useRouter } from 'vue-router';


const DOCUMENT_TITLE = "Confirm project information - Archive your research drive";
document.title = DOCUMENT_TITLE;

const error =ref("");
const router = useRouter();
const driveInfo = getDrive();
const project = getProject();
const owners = membersToString(getProjectOwners(project.members));
const members = membersToString(getProjectMembers(project.members));

function tryContinue() {
    if (formState.areProjectDetailsCorrect === undefined){
        document.title = "Error: " + DOCUMENT_TITLE;
        error.value = "Select Yes if the project information is still correct.";
    } else if (formState.areProjectDetailsCorrect) {
            // Copy project details over as they are correct.
            formState.project = Object.assign({}, getProject());
            router.push("/data-classification");
    } else {
        router.push("/update-details");
    }
}
</script>

<template>
    <main>
    <h1 class="app-title">Archive your research drive</h1>
        <div class="title-section">
            <h2 class="page-title">Check project information</h2>
            <p>Project information describes the files in the research drive and the people who have access and rights to the files. </p> 
            <!-- <p>It is entered when the research drive was requested, but may become incorrect over time. For example, the project may have changed research focus, or people may have joined or left the project.</p> -->
            <p>Correct project information is important for archiving. If required, the information is used to find the right archived files and determine whether to grant or deny access requests.</p> 
        </div> 
    <section class="project-details-card box">
        <h3 class="h2">Project information for {{ driveInfo.name }}</h3>
        <dl class="other-details">
            <dt>Title</dt>
            <dl>{{ project.title}}</dl>
            <dt>Description</dt>
            <dl>{{ project.description}}</dl>
            <dt>Project owner</dt>
            <dl>{{ owners }}</dl>
            <dt>Project members</dt>
            <dl>{{ members }}</dl>
            <dt>Department</dt>
            <dl>{{ project.division }}</dl>
        </dl>
    </section>
    <form novalidate :class="{ error : error }">
        <fieldset>
            <legend class="h2">Is the project information still correct?</legend>
            <p v-if="error" class="error-msg">{{ error }}</p>
            <div class="option-list">
                <input name="confirm-project" type="radio" id="yes-project" :value="true" v-model="formState.areProjectDetailsCorrect">
                <label for="yes-project">Yes, it is.</label>
                <input name="confirm-project" type="radio" id="no-project" :value="false" v-model="formState.areProjectDetailsCorrect">
                <label for="no-project">No, it needs to be updated.</label>
            </div>
        </fieldset>
    </form>
    <section class="forward-btn">
        <a @click.prevent="tryContinue()" class="btn btn-primary">Continue</a>
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
    font-family: NationalBold;
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
    font-family: NationalBold;
}

dt {
    font-family: NationalBold;
}

dt:not(:first-child) {
    margin-top: 1rem;
}
/* table {
    width: 100%; */
/* } */
</style>