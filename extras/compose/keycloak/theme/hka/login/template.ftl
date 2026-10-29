<#-- Seitenrahmen im Look des Portals (src/portal/templates/base.html): Kopf, Inhalt, Fußzeile. -->
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="${lang}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${msg("loginTitle",(realm.displayName!''))}</title>
    <link rel="icon" href="${url.resourcesPath}/img/favicon.ico" />
    <link href="${url.resourcesPath}/kit.css" rel="stylesheet" />
    <script type="importmap">
        {
            "imports": {
                "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js"
            }
        }
    </script>
    <#if scripts??>
        <#list scripts as script>
            <script src="${script}" type="text/javascript"></script>
        </#list>
    </#if>
    <script type="module">
        import { startSessionPolling } from "${url.resourcesPath}/js/authChecker.js";

        startSessionPolling(
            "${url.ssoLoginInOtherTabsUrl?no_esc}"
        );
    </script>
    <#if authenticationSession??>
        <script type="module">
            import { checkAuthSession } from "${url.resourcesPath}/js/authChecker.js";

            checkAuthSession(
                "${authenticationSession.authSessionIdHash}"
            );
        </script>
    </#if>
</head>

<body data-page-id="login-${pageId}">
    <a class="skip" href="#main">${msg("skipLink")}</a>
    <header class="site-header">
        <span class="brand">
            <span class="brand__name">${msg("brandName")}</span>
            <span class="brand__sub">${msg("brandSub")}</span>
        </span>
    </header>
    <div class="shell shell--plain">
        <main id="main" tabindex="-1" class="main">
            <h1 id="kc-page-title"><#nested "header"></h1>

            <#if auth?has_content && auth.showUsername() && !auth.showResetCredentials()>
                <#nested "show-username">
                <p id="kc-username">
                    <span id="kc-attempted-username">${auth.attemptedUsername}</span>
                    <a id="reset-login" href="${url.loginRestartFlowUrl}">${msg("restartLoginTooltip")}</a>
                </p>
            </#if>

            <#-- Bei App-initiierten Aktionen keine Warnung zur noch offenen Aktion zeigen. -->
            <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                <div class="notice<#if message.type = 'error'> notice--warn</#if>" role="<#if message.type = 'error'>alert<#else>status</#if>">
                    <p>${kcSanitize(message.summary)?no_esc}</p>
                </div>
            </#if>

            <#nested "form">

            <#if auth?has_content && auth.showTryAnotherWayLink()>
                <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                    <input type="hidden" name="tryAnotherWay" value="on"/>
                    <a href="#" id="try-another-way"
                       onclick="document.forms['kc-select-try-another-way-form'].requestSubmit();return false;">${msg("doTryAnotherWay")}</a>
                </form>
            </#if>

            <#nested "socialProviders">

            <#if displayInfo>
                <div id="kc-info">
                    <#nested "info">
                </div>
            </#if>
        </main>
    </div>
    <footer class="site-footer" aria-label="${msg("footerLabel")}">
        <p class="site-footer__brand"><strong>${msg("brandName")}</strong>${msg("brandSub")}</p>
        <ul>
            <li><a class="cta" href="#">${msg("footerHelp")}</a></li>
            <li><a class="cta" href="#">${msg("footerPrivacy")}</a></li>
            <li><a class="cta" href="#">${msg("footerImprint")}</a></li>
        </ul>
    </footer>
</body>
</html>
</#macro>
