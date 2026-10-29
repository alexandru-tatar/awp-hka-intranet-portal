<#-- Anmeldeformular im Look des Portals: Felder und Fehlermeldungen nach den Mustern des Kits (04 §7.3). -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "form">
        <#assign loginError = messagesPerField.existsError('username','password')>
        <#if realm.password>
            <p class="prose">${msg("loginIntro")}</p>
            <form id="kc-form-login" action="${url.loginAction}" method="post" novalidate>
                <#if loginError>
                    <div class="error-summary" role="alert" tabindex="-1">
                        <h2>${msg("errorSummaryTitle")}</h2>
                        <ul>
                            <li><a href="#username">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</a></li>
                        </ul>
                    </div>
                </#if>
                <#if !usernameHidden??>
                    <div class="field">
                        <label for="username"><#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if></label>
                        <input id="username" name="username" type="text" value="${(login.username!'')}"
                               autofocus autocomplete="username" dir="ltr"
                               <#if loginError>aria-invalid="true"</#if> />
                    </div>
                </#if>
                <div class="field">
                    <label for="password">${msg("password")}</label>
                    <input id="password" name="password" type="password" autocomplete="current-password" dir="ltr"
                           <#if loginError>aria-invalid="true"</#if> />
                    <#if realm.resetPasswordAllowed>
                        <p class="field__hint"><a href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a></p>
                    </#if>
                </div>
                <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
                <button class="btn btn--primary" name="login" id="kc-login" type="submit">${msg("doLogIn")}</button>
            </form>
        </#if>
    <#elseif section = "info">
        <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
            <p>${msg("noAccount")} <a href="${url.registrationUrl}">${msg("doRegister")}</a></p>
        </#if>
    <#elseif section = "socialProviders">
        <#if realm.password && social?? && social.providers?has_content>
            <h2>${msg("identity-provider-login-label")}</h2>
            <ul>
                <#list social.providers as p>
                    <li><a id="social-${p.alias}" href="${p.loginUrl}">${p.displayName!}</a></li>
                </#list>
            </ul>
        </#if>
    </#if>
</@layout.registrationLayout>
