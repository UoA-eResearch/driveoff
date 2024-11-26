<script lang="ts" setup>
import { getProject } from "@/fixtures";
import { formState } from "@/store";
import { ref } from "vue";
import { useRouter } from "vue-router";

const DOCUMENT_TITLE = "Update project title and description - Archive your research drive"; 
document.title = DOCUMENT_TITLE;


const titleError = ref("");
const descriptionError = ref("");
// If no value from user input yet, set default title and description. 
if (formState.project.title === "") {
    formState.project.title = getProject().title;
}
if (formState.project.description === "") {
    formState.project.description = getProject().description;
}
const router = useRouter();


function tryContinue() {
    if (formState.project.title.trim() === ""){
        titleError.value = "Enter a title for the project."
    } else {
        titleError.value = "";
    }
    if (formState.project.description.trim() === "") {
        descriptionError.value = "Enter a description for the project."
    } else {
        descriptionError.value = "";
    }
    if (titleError.value !== "" || descriptionError.value !== "") {
        // If there's an error, do not advance to the next page.
        document.title = "Error: " + DOCUMENT_TITLE;
        return;
    }
    // Otherwise, go to the next page
    router.push("data-classification");
}
</script>
<template>
    <main>
        <h1 class="app-title">Update project information</h1>
        <div class="title-section">
            <h2 class="page-title">About your work</h2>
        </div>
        <form novalidate @submit.prevent="tryContinue()">
            <div class="form-group" :class="{ error : titleError }">
                <label for="project-title" class="h2">Title</label>
                <p v-if="titleError" class="error-msg">{{ titleError }}</p>
                <input type="text" id="project-title" v-model="formState.project.title">
            </div>
            <div class="form-group" :class="{ error : descriptionError }">
                <label for="project-description" class="h2">Description</label>
                <p v-if="descriptionError" class="error-msg">{{ descriptionError }}</p>
                <textarea id="project-description" v-model="formState.project.description"></textarea>
            </div>
        </form>
        <section class="forward-btn">
            <a @click.prevent="tryContinue()" class="btn btn-primary">Continue</a>
        </section>
    </main>

</template>

<style scoped>
    textarea {
        min-height: 10rem;
    }
</style>