<script lang="ts" setup>
import { appendDriveInfoApiV1SubmissionPost } from '@/client';
import { getProjectMembers, getProjectOwners, membersToString } from '@/models/helpers';
import { formState, requestInfo } from '@/store';
import { useRouter } from 'vue-router';

const DOCUMENT_TITLE = "Check your answers - Archive your research drive";
document.title = DOCUMENT_TITLE;

const router = useRouter();
const projectOwners = membersToString(getProjectOwners(requestInfo.project.members));
const projectMembers = membersToString(getProjectMembers(requestInfo.project.members));

// Display changed title and description if available, original if not.
const projectTitle = formState.projectChanges.title || requestInfo.project.title;
const projectDescription = formState.projectChanges.description || requestInfo.project.description;

// If the user has stated the details aren't correct, the Change links should go to the Update page. 
const projectInfoChangeLink = formState.areProjectDetailsCorrect ? "/check-details" : "/update-details"; 

async function submit(){
    const dataClassification = formState.dataClassification;
    const retentionPeriod = formState.retentionPeriod;
    if (dataClassification === null || retentionPeriod === null ){
        // Form is not yet complete!
        // This should not happen.
        return;
    }
    const submission = {
        dataClassification,
        retentionPeriodYears: retentionPeriod,
        isCompleted: true,
        driveName: requestInfo.drive.name,
        projectChanges: formState.projectChanges

    }
    const req = await appendDriveInfoApiV1SubmissionPost({
        body: submission
    });
    if (req.response.ok) {
        router.push("/finish");
    } else {
        router.push("/service-error")
    }
}
</script>

<template>
    <h1 class="app-title">Archive your research drive</h1>
    <div class="title-section">
        <h2 class="page-title">Check your answers before sending your request</h2>
    </div>
        <h3 class="h2">Project details</h3>
    <table>
        <colgroup>
        <col class="part-name-col" />
        <col />
        <col class="change-btn-col" />
        </colgroup>
        <tbody>
            <tr>
                <td>Project name</td>
                <td>{{  projectTitle  }}</td>
                <td><RouterLink :to="projectInfoChangeLink">Change</RouterLink></td>
            </tr>
            <tr>
                <td>Project description</td>
                <td> {{ projectDescription }}</td>
                <td><RouterLink :to="projectInfoChangeLink">Change</RouterLink></td>
            </tr>
            <tr>
                <td>Project owner</td>
                <td>{{ projectOwners }}</td>
                <td><!--<a href="#" class="btn-link">Change</a>--></td>
            </tr>
            <tr>
                <td>Project members</td>
                <td>{{ projectMembers }}</td>
                <td><!--<a href="#" class="btn-link">Change</a>--></td>
            </tr>
            <tr>
                <td>Department</td>
                <td>{{  requestInfo.project.division }}</td>
                <td><!--<a href="#" class="btn-link">Change</a>--></td>
            </tr>
        </tbody>
    </table>

    <h3 class="h2">Archive details</h3>
    <table>
        <colgroup>
        <col class="part-name-col" />
        <col />
        <col class="change-btn-col" />
        </colgroup>
        <tbody>
            <tr>
                <td>Data classification</td>
                <td>{{ formState.dataClassification }}</td>
                <td><RouterLink to="/data-classification">Change</RouterLink></td>
            </tr>
            <tr>
                <td>Retention period</td>
                <td>{{ formState.retentionPeriod }} years from today</td>
                <td><RouterLink to="/retention-period">Change</RouterLink></td>
            </tr>
        </tbody>
    </table>
    <h3 class="h2">Send this request</h3>
    By sending this request you are confirming that the details are correct and you wish to archive this drive.
    <section class="forward-btn">
        <a @click="submit()" class="btn btn-primary">Submit</a>
    </section>
</template>

<style scoped>
td {
    padding: 0.5rem;
    border-bottom: 1px solid gray;
    /* background-color: lightgray; */
    
}
td:first-child {
    font-family: NationalBold;
}

td:last-of-type {
    text-align: end;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

table {
    width: 100%;
    margin-bottom: 2rem;
    table-layout: fixed;;
}

.part-name-col {
    width: 30%;
}

.change-btn-col {
    width: 20%;
}
</style>