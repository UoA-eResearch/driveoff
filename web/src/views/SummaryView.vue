<script setup lang="ts">
import { useRouter } from 'vue-router';
import { ref } from 'vue';
import { formState } from '@/store';
import { getDrive } from '@/fixtures';


const DOCUMENT_TITLE = "Confirm research drive - Archive your research drive"; 
document.title = DOCUMENT_TITLE;

// const isCorrectDrive = ref();
const error = ref("");
const router = useRouter();
const driveInfo = getDrive();

function tryContinue() {
    if (formState.isCorrectDrive === undefined){
        document.title = "Error: " + DOCUMENT_TITLE;
        error.value = "Select Yes if this is research drive you wanted to archive."
    } else {
        if (formState.isCorrectDrive) {
            router.push("/check-details");
        } else {
            router.push("/unable-to-archive")
        }
    }
}

</script>

<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <section :class="{ error : error }">
            <div class="title-section">
                <h2 class="page-title">Is this the drive you want to archive?</h2>
                <p v-if="error" class="error-msg">{{ error }}</p>
            </div>
        <section class="drive-details-card box">
            <h3 class="drive-name">{{ driveInfo.name }}</h3>
            <p class="storage-size">{{ driveInfo.allocated_gb }} GB</p>
            <a href="#" class="btn-link">See files in drive...</a>
        </section>
        <form novalidate>
        <fieldset>
            <div class="option-list">
                <input name="confirm-drive" type="radio" id="yes-drive" :value="true" v-model="formState.isCorrectDrive">
                <label for="yes-drive">Yes, it is.</label>
                <input name="confirm-drive" type="radio" id="no-drive" :value="false" v-model="formState.isCorrectDrive">
                <label for="no-drive">No, it's not.</label>
            </div>
        </fieldset>
    </form>
    </section>
        <section class="forward-btn">
            
            <a @click.prevent="tryContinue()" class="btn btn-primary">Continue</a>

        </section>
    </main>
</template>

<style scoped>
td {
    padding: 0.5rem;
}
td:first-child {
    font-family: NationalBold;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

table {
    width: 100%;
}


.drive-details-card {
    padding-left: 1rem;
    padding: 1rem;
    margin: 2rem 0;
    width: fit-content;
}

.drive-name {
    font-size: 1.3rem;
    font-weight: bold;
}
</style>